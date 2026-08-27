import importlib.util
import importlib.machinery
from pathlib import Path
import sysconfig

stdlib = Path(sysconfig.get_path("stdlib"))
ast_path = stdlib / "ast.py"

spec = importlib.util.spec_from_file_location("stdlib_ast", ast_path)
stdlib_ast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stdlib_ast)


def _find(name: str, paths: list[Path]):
    """Resolve one dotted component in `paths` -> (file, search_locations), or None.

    `file` is None for a namespace package; `search_locations` is empty for a module.
    """
    spec = importlib.machinery.PathFinder.find_spec(name, [str(p) for p in paths])
    if spec is None:
        return None
    file = None
    if spec.has_location and spec.origin:
        file = Path(spec.origin).resolve()
    locations = [Path(p) for p in (spec.submodule_search_locations or [])]
    return file, locations


def _resolve_dotted(parts: list[str], paths: list[Path], root: Path):
    """Walk `a.b.c` from `paths` -> (files, search_locations).

    `files` are the __init__/module files on the chain that live under `root`;
    `search_locations` belong to the last component (None for a plain module).
    """
    files: list[Path] = []
    for part in parts:
        if paths is None:
            return files, None
        hit = _find(part, paths)
        if hit is None:
            return files, None
        file, locations = hit
        if file is not None and file.suffix == ".py" and root in file.parents:
            files.append(file)
        paths = locations if locations else None
    return files, paths


def _imports_of(tree: stdlib_ast.AST, current_file: Path, root: Path) -> list[Path]:
    """Project-local files imported by `tree` (absolute, resolved)."""
    top = [root]
    out: list[Path] = []
    for node in stdlib_ast.walk(tree):
        if isinstance(node, stdlib_ast.Import):
            for alias in node.names:
                out.extend(_resolve_dotted(alias.name.split("."), top, root)[0])
        elif isinstance(node, stdlib_ast.ImportFrom):
            if node.level == 0:
                base = top
                parts = node.module.split(".") if node.module else []
            else:
                package_dir = current_file.parent
                for _ in range(node.level - 1):
                    package_dir = package_dir.parent
                base = [package_dir]
                parts = node.module.split(".") if node.module else []
            files, sub = _resolve_dotted(parts, base, root)
            out.extend(files)
            if sub is not None:
                for alias in node.names:
                    if alias.name != "*":
                        out.extend(_resolve_dotted([alias.name], sub, root)[0])
    return out


def load_program_ast(main_file: Path) -> list[stdlib_ast.AST]:
    """ASTs of the entry file (always first) and every project-local module it reaches."""
    main_file = Path(main_file).resolve()
    root = main_file.parent
    seen = {main_file}
    queue = [main_file]
    modules: list[stdlib_ast.AST] = []
    while queue:
        file = queue.pop(0)
        tree = stdlib_ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        modules.append(tree)
        for dep in _imports_of(tree, file, root):
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    return modules

def check_code_structure(modules: list[stdlib_ast.AST], expected: dict[str, list[str]]) -> list[str]:
    errors = []
    # for each module, check if it contains the expected classes and methods
    surplus = list(expected.keys())
    for module in modules:
        classes = {}
        for node in stdlib_ast.walk(module):
            if isinstance(node, stdlib_ast.ClassDef):
                classes[node.name] = node
        for class_name, methods in expected.items():
            if class_name in classes:
                class_node = classes[class_name]
                method_names = [n.name for n in class_node.body if isinstance(n, stdlib_ast.FunctionDef)]
                for method in methods:
                    if method not in method_names:
                        errors.append(f"Method `{method}` not found in class `{class_name}`")
                for method in class_node.body:
                    if isinstance(method, stdlib_ast.FunctionDef):
                        waiver = {"Node": ["generate", "new_id"], "Code": ["append", "dump"]}
                        function = "FuncDec" in expected
                        if method.name not in methods and method.name != "__init__":
                            if not function or ((class_name not in waiver or method.name not in waiver[class_name]) and method.name != "generate"):
                                errors.append(f"Unexpected method `{method.name}` found in class `{class_name}`")
                del classes[class_name]
                if class_name in surplus:
                    surplus.remove(class_name)
        for class_name in classes.keys():
            if not "FuncDec" in expected or class_name != "Code":
                errors.append(f"Unexpected class `{class_name}` found")
    for class_name in surplus:
        errors.append(f"Expected class `{class_name}` not found")
    return errors

def check_static_classes(modules: list[stdlib_ast.AST], st: bool = False, generate: bool = False) -> list[str]:
    errors = []
    classes = [node for module in modules for node in stdlib_ast.walk(module) if isinstance(node, stdlib_ast.ClassDef) and node.name in ["Parser", "PrePro", "Code", "Node"]]

    for parser in classes:
        # check if Parser methods are static
        for method_node in parser.body:
            if isinstance(method_node, stdlib_ast.FunctionDef):
                if method_node.name == "__init__" and parser.name != "Node":
                    errors.append(f"Class `{parser.name}` should not have a constructor method")
                elif method_node.name == "run" and parser.name == "Parser":
                    if len(method_node.args.args) > 1:
                        errors.append(f"Method `{method_node.name}` should have only 1 argument")

                    # Check if there is no SymbolTable() created and no print in run
                    for node in stdlib_ast.walk(method_node):
                        if isinstance(node, stdlib_ast.Call):
                            if st and isinstance(node.func, stdlib_ast.Name) and node.func.id == "SymbolTable":
                                errors.append(f"Method `run` in class `Parser` should not create a SymbolTable instance")
                            if isinstance(node.func, stdlib_ast.Name) and node.func.id == "print":
                                errors.append(f"Method `run` in class `Parser` should not contain print statements")

                elif method_node.name == "filter" and parser.name == "PrePro":
                    if len(method_node.args.args) > 0:
                        first_arg = method_node.args.args[0].arg
                        if first_arg == "self":
                            errors.append(f"Method `{method_node.name}` in class `{parser.name}` should be static")
                    if len(method_node.args.args) > 1:    
                        errors.append(f"Method `{method_node.name}` should have only 1 argument")
                elif method_node.name == "new_id" and parser.name == "Node":
                    if len(method_node.args.args) > 0:
                        first_arg = method_node.args.args[0].arg
                        if first_arg == "self":
                            errors.append(f"Method `{method_node.name}` in class `{parser.name}` should be static")    
                        else:
                            errors.append(f"Method `{method_node.name}` should not have any arguments")
                elif len(method_node.args.args) > 0 and parser.name == "Parser":
                    first_arg = method_node.args.args[0].arg
                    if first_arg == "self":
                        errors.append(f"Method `{method_node.name}` in class `{parser.name}` should be static")                
                    elif len(method_node.args.args) > 0:
                        errors.append(f"Method `{method_node.name}` should not have arguments")

        if parser.name == "Parser":
            found = False
            # check if lexer is a static attribute of Parser
            for node in parser.body:
                if isinstance(node, stdlib_ast.Assign):
                    for target in node.targets:
                        if isinstance(target, stdlib_ast.Name) and target.id == "lexer":
                            found = True
                            
                    if found:
                        break
            else:
                errors.append("`lexer` should be a static attribute in class `Parser`")

        elif parser.name == "Code":
            found = False
            # check if instructions is a static attribute of Code
            for node in parser.body:
                if isinstance(node, stdlib_ast.Assign):
                    for target in node.targets:
                        if isinstance(target, stdlib_ast.Name) and target.id == "instructions":
                            found = True
                    if found:
                        break
            else:
                errors.append("`instructions` should be a static attribute in class `Code`")

        elif parser.name == "Node" and generate:
            found = False
            # check if instructions is a static attribute of Code
            for node in parser.body:
                if isinstance(node, stdlib_ast.Assign):
                    for target in node.targets:
                        if isinstance(target, stdlib_ast.Name) and target.id == "id":
                            found = True
                    if found:
                        break
            else:
                errors.append("`id` should be a static attribute in class `Node`")

    return errors

def check_ast_nodes(modules: list[stdlib_ast.AST]) -> list[str]:
    errors = []
    others = ["Parser", "Lexer", "Token", "SymbolTable", "Variable", "PrePro", "Code"]
    nodes = [node for module in modules for node in stdlib_ast.walk(module) if isinstance(node, stdlib_ast.ClassDef) and node.name not in others]
    # check the methods of the AST classes
    for node in nodes:
        for method_node in node.body:
            if isinstance(method_node, stdlib_ast.FunctionDef):
                if method_node.name == "__init__":
                    # check if __init__ has only self, value and children args
                    error = False
                    for arg in method_node.args.args:
                        if arg.arg not in ["self", "value", "children"]:
                            error = True
                            # errors.append(f"Constructor of `{node.name}` has unexpected argument `{arg.arg}`")
                    if error or len(method_node.args.args) != 3:
                        errors.append(f"Constructor of `{node.name}` should have only `self`, `value` and `children` arguments")
                elif method_node.name in ["evaluate", "generate"]:
                    if len(method_node.args.args) == 1 and method_node.args.args[0].arg != "self":
                        errors.append(f"Unexpected argument {method_node.args.args[0].arg} in Method `{method_node.name}` in class `{node.name}`")
                    elif len(method_node.args.args) == 2 and \
                        method_node.args.args[0].arg != "self" and \
                        method_node.args.args[1].arg != "st":
                        errors.append(f"Unexpected argument `{method_node.args.args[0].arg}` in Method `{method_node.name}` in class `{node.name}`")
                    elif len(method_node.args.args) == 0 or len(method_node.args.args) > 2:
                        errors.append(f"Wrong arguments for Method `{method_node.name}` in class `{node.name}`")
    return errors


def check_main_function(modules: list[stdlib_ast.AST], expected: dict[str, list[str]]) -> list[str]:
    errors = []
    main = modules[0]
    #check if there is a if __name__ == "__main__": block
    for node in stdlib_ast.walk(main):
        if isinstance(node, stdlib_ast.If):
            if isinstance(node.test, stdlib_ast.Compare):
                left = node.test.left
                comparators = node.test.comparators
                if (isinstance(left, stdlib_ast.Name) and left.id == "__name__" and
                    len(comparators) == 1 and
                    isinstance(comparators[0], stdlib_ast.Constant) and
                    comparators[0].value == "__main__"):
                    break
    else:
        errors.append("Missing `if __name__ == '__main__':` block in main")

    # check if main calls Parser.run()
    if expected is not None:
        for node in stdlib_ast.walk(main):
            if isinstance(node, stdlib_ast.Call):
                if isinstance(node.func, stdlib_ast.Attribute):
                    if node.func.attr == "run":
                        if isinstance(node.func.value, stdlib_ast.Name):
                            if node.func.value.id == "Parser":
                                break
        else:
            errors.append("Missing call to `Parser.run()` in main")

    # check if there is SymbolTable created in main
    if expected is not None and "SymbolTable" in expected:
        for node in stdlib_ast.walk(main):
            if isinstance(node, stdlib_ast.Call):
                if isinstance(node.func, stdlib_ast.Name):
                    if node.func.id == "SymbolTable":
                        break
        else:
            errors.append("Missing creation of `SymbolTable` instance in main")

    # check if there is a variable.evaluate call on the main AST node
    if expected is not None and "Node" in expected:
        for node in stdlib_ast.walk(main):
            if isinstance(node, stdlib_ast.Call):
                if isinstance(node.func, stdlib_ast.Attribute):
                    if node.func.attr == "evaluate":
                        break
        else:
            errors.append("Missing call to `evaluate()` on the main AST node in main")

    return errors

def check_snake_case(code: str) -> list[str]:
    return []

def check_code_style(code: str) -> list[str]:
    return []

def check(file: str, expected: dict[str, list[str]]) -> list[str]:
    errors = []
    modules = load_program_ast(Path(file))
    errors.extend(check_main_function(modules, expected))
    errors.extend(check_code_structure(modules, expected))
    errors.extend(check_static_classes(modules, "SymbolTable" in expected, "generate" in expected.get("Node", [])))
    errors.extend(check_ast_nodes(modules))

    # Read all code (including imports) to check style
    code = ""

    errors.extend(check_code_style(code))
    errors.extend(check_snake_case(code))
    return errors