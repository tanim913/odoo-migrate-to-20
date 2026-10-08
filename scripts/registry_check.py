"""Registry checks that need the loaded Odoo 20 registry (run after the module installs).

    MODULE_DIRS=/path/to/addons/my_module[,/path/to/other] \
        odoo-bin shell -d <db with the modules installed> --no-http < registry_check.py

Reports, for the classes defined in those module folders:

- missing-method: a field whose compute / inverse / search method does not exist on the model.
  Typical when a field definition was copied whole from Odoo 17 core and the 20 compute was renamed
  or removed: the install or the first recompute fails.
- dead-super: a method that calls super().<same name>() although no class after it in the model's
  MRO defines that method. The core hook was renamed or removed: the override is never called by
  Odoo, and its super() call would raise. Uses the real MRO, so same-named methods of other models
  and mixins are not confused (unlike a name-based static scan).

Prints one line per finding and "REGISTRY_CHECK: N problem(s)". Read-only.
"""
import ast
import inspect
import os
import textwrap

dirs = [d.rstrip('/') + '/' for d in os.environ.get('MODULE_DIRS', '').split(',') if d]
if not dirs:
    raise SystemExit('Set MODULE_DIRS to the module folder(s) to check')


def own_file(cls):
    try:
        path = inspect.getsourcefile(cls) or ''
    except TypeError:
        return False
    return any(path.startswith(d) for d in dirs)


def calls_super_same(func, name):
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    except (OSError, TypeError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == name
                and isinstance(node.func.value, ast.Call) and getattr(node.func.value.func, 'id', '') == 'super'):
            return True
    return False


problems = []
for model_name in sorted(env.registry):  # noqa: F821 - provided by odoo-bin shell
    model = env.registry[model_name]  # noqa: F821
    mro = model.__mro__
    own = [cls for cls in mro if own_file(cls)]
    if not own:
        continue
    # 1. compute / inverse / search methods that do not exist
    own_names = {name for cls in own for name in vars(cls)}
    for fname, field in model._fields.items():
        if fname not in own_names:
            continue
        for attr in ('compute', 'inverse', 'search'):
            method = getattr(field, attr, None)
            if isinstance(method, str) and not hasattr(model, method):
                problems.append(f"missing-method {model_name}.{fname}: {attr}='{method}' does not exist")
    # 2. super() calls to a method nobody defines after this class
    for index, cls in enumerate(mro):
        if cls not in own:
            continue
        for name, value in vars(cls).items():
            if not callable(value) or name.startswith('__'):
                continue
            if not calls_super_same(value, name):
                continue
            if not any(name in vars(parent) for parent in mro[index + 1:]):
                problems.append(f"dead-super {model_name}.{name} ({inspect.getsourcefile(cls)}): "
                                "super() target no longer exists in Odoo 20")

for line in sorted(set(problems)):
    print(line)
print(f"REGISTRY_CHECK: {len(set(problems))} problem(s)")
