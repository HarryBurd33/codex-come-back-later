"""Catch lost imports when exporting the standalone helper subset."""
import builtins
from pathlib import Path
import symtable
import unittest


class ExportBindingsTest(unittest.TestCase):
    def test_each_referenced_global_has_a_module_or_builtin_binding(self):
        for path in (Path(__file__).resolve().parents[1]/'scripts').glob('*.py'):
            table=symtable.symtable(path.read_text(),str(path),'exec')
            defined={s.get_name() for s in table.get_symbols() if s.is_assigned() or s.is_imported() or s.is_namespace()}
            defined|=set(vars(builtins))|{'__name__','__file__','__package__','__doc__'}
            def visit(scope):
                for symbol in scope.get_symbols():
                    if symbol.is_referenced() and symbol.is_global():
                        self.assertIn(symbol.get_name(),defined,f'{path.name}:{scope.get_name()}')
                for child in scope.get_children():visit(child)
            visit(table)
