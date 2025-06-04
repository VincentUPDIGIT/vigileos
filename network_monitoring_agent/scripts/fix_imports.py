#!/usr/bin/env python3
"""
Fix imports in the project to use absolute imports.
"""

import re
from pathlib import Path

def fix_imports_in_file(file_path: Path):
    """Fix imports in a single file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Get the relative path from src directory
        src_dir = file_path.parent
        while src_dir.name != "src" and src_dir.parent != src_dir:
            src_dir = src_dir.parent
        
        if src_dir.name != "src":
            return
        
        # Get the package path
        rel_path = file_path.parent.relative_to(src_dir)
        package_parts = list(rel_path.parts) if rel_path.parts != ('.',) else []
        
        # Fix imports based on file location
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            # Skip comments and empty lines
            if line.strip().startswith('#') or not line.strip():
                new_lines.append(line)
                continue
            
            # Fix relative imports
            if 'from .' in line and 'import' in line:
                # Extract the import parts
                match = re.match(r'(\s*)from\s+(\.+)([a-zA-Z_][a-zA-Z0-9_]*)\s+import\s+(.+)', line)
                if match:
                    indent, dots, module, imports = match.groups()
                    
                    # Calculate the absolute module path
                    if len(dots) == 1:  # from .module
                        if package_parts:
                            abs_module = '.'.join(package_parts + [module])
                        else:
                            abs_module = module
                    elif len(dots) == 2:  # from ..module
                        if len(package_parts) > 0:
                            abs_module = '.'.join(package_parts[:-1] + [module])
                        else:
                            abs_module = module
                    else:
                        abs_module = module
                    
                    new_line = f"{indent}from {abs_module} import {imports}"
                    new_lines.append(new_line)
                    continue
            
            # Fix direct module imports without relative dots
            if line.strip().startswith('from ') and 'import' in line and not line.strip().startswith('from .'):
                match = re.match(r'(\s*)from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import\s+(.+)', line)
                if match:
                    indent, module, imports = match.groups()
                    
                    # Check if this is a local module (exists in same directory or parent)
                    current_dir = file_path.parent
                    module_file = current_dir / f"{module}.py"
                    
                    if module_file.exists():
                        # It's a local module, make it relative to package
                        if package_parts:
                            abs_module = '.'.join(package_parts + [module])
                        else:
                            abs_module = module
                        new_line = f"{indent}from {abs_module} import {imports}"
                        new_lines.append(new_line)
                        continue
                    
                    # Check parent directories for the module
                    found = False
                    for parent_pkg in ['agent', 'models', 'platforms', 'utils', 'apis']:
                        parent_dir = src_dir / parent_pkg
                        if (parent_dir / f"{module}.py").exists():
                            abs_module = f"{parent_pkg}.{module}"
                            new_line = f"{indent}from {abs_module} import {imports}"
                            new_lines.append(new_line)
                            found = True
                            break
                    
                    if not found:
                        new_lines.append(line)
                    continue
            
            new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
        
        if new_content != original_content:
            with open(file_path, 'w') as f:
                f.write(new_content)
            print(f"Fixed imports in {file_path}")
        
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

def main():
    """Fix all imports in the project."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src"
    
    # Find all Python files
    python_files = list(src_dir.rglob("*.py"))
    
    for file_path in python_files:
        if file_path.name != "__init__.py":  # Skip __init__.py files
            fix_imports_in_file(file_path)
    
    print(f"Processed {len(python_files)} files")

if __name__ == '__main__':
    main()