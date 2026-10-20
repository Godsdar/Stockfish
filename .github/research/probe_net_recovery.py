"""Exercise failed NNUE loads and explicit recovery through the UCI interface."""
import argparse
import json
import pathlib
import queue
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import uuid


class Engine:
    def __init__(self, binary, cwd):
        self.process = subprocess.Popen([str(binary)], cwd=cwd, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding='utf-8', errors='replace', bufsize=1)
        self.lines = queue.Queue()
        self.log = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.command('uci')
        lines = self.until(lambda s: s == 'uciok')
        self.default = next(s.split(' default ', 1)[1] for s in lines
                            if s.startswith('option name EvalFile '))
        self.ready()

    def _read(self):
        for line in self.process.stdout:
            self.lines.put(line.rstrip())
        self.lines.put(None)

    def command(self, text):
        self.log.append('> ' + text)
        self.process.stdin.write(text + '\n')
        self.process.stdin.flush()

    def until(self, predicate):
        result = []
        while True:
            line = self.lines.get(timeout=60)
            if line is None:
                raise RuntimeError('engine exited: ' + '\n'.join(self.log[-20:]))
            self.log.append(line)
            result.append(line)
            if predicate(line):
                return result

    def ready(self):
        self.command('isready')
        return self.until(lambda s: s == 'readyok')

    def configure(self, name):
        self.command('setoption name EvalFile value ' + str(name))
        self.ready()

    def evaluation(self):
        self.command('position startpos')
        self.command('eval')
        lines = self.ready()
        raw = next(int(m.group(1)) for s in lines
                   if (m := re.search(r'NNUE evaluation\s+([+-]?\d+) \(side to move', s)))
        return raw

    def search(self):
        self.command('ucinewgame')
        self.ready()
        self.command('position startpos')
        self.command('go depth 8')
        lines = self.until(lambda s: s.startswith('bestmove '))
        final = next(s for s in reversed(lines) if s.startswith('info depth 8 '))
        # Time, NPS and hashfull are not part of the deterministic comparison.
        return {key: re.search(pattern, final).group(1) for key, pattern in
                [('score', r' score (cp -?\d+|mate -?\d+)'), ('nodes', r' nodes (\d+)'),
                 ('pv', r' pv (.*)')]}

    def close(self):
        if self.process.poll() is None:
            self.command('quit')
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.reader.join(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('binary', type=pathlib.Path)
    parser.add_argument('network', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    parser.add_argument('--expect-fixed', action='store_true')
    args = parser.parse_args()
    binary, network = args.binary.resolve(), args.network.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    with network.open('rb') as f:
        header = f.read(12)
        _, _, desc_size = struct.unpack('<III', header)
        prefix = header + f.read(desc_size + 4)
    results = []
    scenarios = ['truncated-default', 'truncated-custom', 'truncated-repeat',
                 'missing-file', 'empty-file', 'trailing-data', 'reject-export',
                 'restore-empty-default', 'successful-directory-fallback']
    for scenario in scenarios:
        with tempfile.TemporaryDirectory(prefix='sf-net-recovery-') as temp:
            directory = pathlib.Path(temp)
            bad = directory / 'broken.nnue'
            if scenario == 'missing-file':
                pass
            elif scenario == 'empty-file':
                bad.write_bytes(b'')
            elif scenario == 'trailing-data':
                shutil.copyfile(network, bad)
                with bad.open('ab') as f: f.write(b'\0')
            else:
                bad.write_bytes(prefix + b'\0' * 1024)
            engine = Engine(binary, directory)
            fallback = None
            try:
                good = engine.default
                if scenario == 'truncated-custom':
                    good = directory / 'custom.nnue'
                    shutil.copyfile(network, good)
                    engine.configure(good)
                before_eval, before_search = engine.evaluation(), engine.search()
                if scenario == 'successful-directory-fallback':
                    fallback = binary.parent / ('recovery-' + uuid.uuid4().hex + '.nnue')
                    shutil.copyfile(network, fallback)
                    bad.rename(directory / fallback.name)
                    engine.configure(fallback.name)
                else:
                    engine.configure(bad)
                if scenario == 'truncated-repeat':
                    engine.configure(bad)
                if scenario == 'reject-export':
                    exported = directory / 'rejected.nnue'
                    engine.command('export_net ' + str(exported))
                    export_lines = engine.ready()
                    passed = not exported.exists() and any(
                        'No network file is currently loaded' in s for s in export_lines)
                    record = dict(scenario=scenario, passed=passed,
                                  exported=exported.exists(), messages=export_lines)
                else:
                    if scenario != 'successful-directory-fallback':
                        engine.configure('' if scenario == 'restore-empty-default' else good)
                    after_eval, after_search = engine.evaluation(), engine.search()
                    record = dict(scenario=scenario,
                                  passed=(before_eval == after_eval and before_search == after_search),
                                  before_eval=before_eval, after_eval=after_eval,
                                  before_search=before_search, after_search=after_search)
                results.append(record)
            finally:
                engine.close()
                if fallback is not None:
                    fallback.unlink(missing_ok=True)
                (args.output / (scenario + '.log')).write_text('\n'.join(engine.log) + '\n')
            print(json.dumps(results[-1]), flush=True)
    (args.output / 'results.json').write_text(json.dumps(
        dict(binary=str(binary), network=str(network), results=results), indent=2) + '\n')
    if args.expect_fixed and not all(r['passed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
