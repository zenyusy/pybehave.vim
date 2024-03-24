from itertools import chain
from pathlib import Path
import ast
import sys

importerr = False

try:
    import parse
    import vim
    from behave import parser as behave_parser
    from behave import runner_util
    from behave.step_registry import registry
except ImportError:
    importerr = True


def get_filename():
    return vim.current.buffer.name.strip()


def findmain():
    if importerr:
        print("importerr")
        return
    filename = get_filename()
    feat_dir = find_feat_dir(filename)
    if not feat_dir:
        print("structure not supported")
        return
    sys.path.insert(0, str(feat_dir.parent))
    if (envfile := feat_dir / "environment.py").exists():
        runner_util.exec_file(str(envfile))
    filetype = vim.current.buffer.options["filetype"] or ""
    if isinstance(filetype, bytes):
        filetype = filetype.decode()
    if filetype == "cucumber":
        find_py(filename, feat_dir)
    else:
        find_feat(filename, feat_dir)


def find_feat_dir(filename):
    ret = Path(filename).expanduser().absolute()
    if not ret.is_dir():
        ret = ret.parent
    SEARCH_EFFORT = range(9)
    ret0 = ret
    for _ in SEARCH_EFFORT:
        if ret0.is_dir() and tuple(ret0.glob("features/*.feature")):
            return ret0 / "features"
        ret0 = ret0.parent
    ret0 = ret
    for _ in SEARCH_EFFORT:
        if ret0.is_dir() and (ret0 / "environment.py").exists():
            return ret0
        ret0 = ret0.parent
    for _ in SEARCH_EFFORT:
        if ret.is_dir() and tuple(ret.glob("*.feature")):
            return ret
        ret = ret.parent
    return None


class StepLocation:
    def __init__(self, step_type, desc, name, file, line):
        self.step_type = step_type
        self.desc = desc
        self.name = name
        self.file = file
        self.line = line


def find_feat(filename, feat_dir):
    if not filename.endswith(".py"):
        print("file type not supported")
        return
    step_deco = get_step_deco_in_py(vim.current.buffer, vim.current.window.cursor[0])
    if not step_deco:
        print("no deco")
        return
    ret = []
    is_general_step = step_deco.step_type == "step"
    for step_feat in filter(
        lambda e: is_general_step or e.step_type == step_deco.step_type,
        find_step_in_feat(feat_dir),
    ):
        if parse.parse(step_deco.name, step_feat.name):
            ret.append(step_feat)
    if not ret:
        print("no result")
        return
    if len(ret) == 1:
        ret0 = ret[0]
        vim.command(f"edit +{ret0.line} {ret0.file}")
    vim.funcs.setloclist(
        0, [{"filename": l.file, "lnum": l.line, "text": l.desc} for l in ret]
    )
    vim.command("lopen {}".format(min(len(ret), 6)))


def find_step_in_feat(feat_dir: Path):
    for feat in feat_dir.rglob("*.feature"):
        feat_data = feat.read_text()
        if len(feat_data) < 16:
            continue
        feature = behave_parser.parse_feature(feat_data, filename=str(feat))
        if not feature:
            print(f"{feat} no parse")
            return
        for scenario in filter(None, chain((feature.background,), feature.scenarios)):
            is_scenario_outline = scenario.type == "scenario_outline"
            for step in scenario.steps:
                name = step.name
                if is_scenario_outline:
                    try:
                        table = scenario.examples[0].table
                        for param in table.headings:
                            name = name.replace(f"<{param}>", table[0][param])
                    except:
                        pass
                yield StepLocation(
                    step.step_type, step.name, name, feature.filename, step.line
                )


def get_step_in_py(buf):
    for obj in ast.parse("\n".join(buf)).body:
        if obj.__class__.__name__ == "FunctionDef":
            for deco in obj.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and deco.func.id in ("step", "given", "when", "then")
                    and deco.args
                ):
                    yield StepLocation(
                        deco.func.id,
                        f"@{deco.func.id}({deco.args[0].s})",
                        deco.args[0].s,
                        None,
                        deco.lineno,
                    )


def get_step_deco_in_py(buf, lineno):
    ret = None
    for deco in get_step_in_py(buf):
        if deco.line > lineno:
            break
        ret = deco
    return ret


def find_py(filename: str, base_dir: Path) -> None:
    if not filename.endswith(".feature"):
        print("file not supported")
        return
    cur_line = vim.current.line.lstrip()
    # vim.current.buffer[vim.current.window.cursor[0]-1].lstrip()
    to_match = cur_line[cur_line.find(" ") + 1 :].lstrip()
    runner_util.load_step_modules([str(base_dir / "steps")])
    for arr in registry.steps.values():
        for step in arr:
            if step.match(to_match):
                file = step.location.abspath()
                line = step.location.line
                vim.command(f"edit +{line} {file}")
                return
    print("not found")
