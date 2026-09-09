import os
import ast
import unittest

class TestSprint7Security(unittest.TestCase):
    def test_no_unsafe_dynamic_execution_exists(self):
        banned = {'eval', 'exec', 'pickle'}
        found = []
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        for root, dirs, files in os.walk(project_root):
            # CORREÇÃO: Separa os diretórios via os.sep para não bloquear acidentalmente pastas que contenham as strings (ex: "not_venv")
            parts = root.split(os.sep)
            if any(ign in parts for ign in ['.venv', 'venv', 'env', '__pycache__', '.git']):
                continue
                
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    path = os.path.join(root, file)
                    with open(path, 'r', encoding='utf-8') as f:
                        try:
                            tree = ast.parse(f.read())
                            for node in ast.walk(tree):
                                if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in banned:
                                    found.append(f"{file}:{getattr(node.func, 'id', '')}")
                        except SyntaxError:
                            self.fail(f"FALHA ESTRITA: Erro de sintaxe no arquivo {file}.")
                        except UnicodeDecodeError:
                            self.fail(f"FALHA ESTRITA: Arquivo binário mascarado de .py {file}.")
                            
        self.assertEqual(len(found), 0, f"Found unsafe execution: {found}")