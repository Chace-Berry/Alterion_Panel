"""
Backend Framework Detection Service
Automatically detects Django, FastAPI, Node.js frameworks and extracts API endpoints and models.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import ast


class BackendDetector:
    """
    Detects backend frameworks and extracts API structure.
    """
    
    FRAMEWORK_SIGNATURES = {
        'django': {
            'files': ['manage.py', 'wsgi.py', 'asgi.py'],
            'patterns': [r'from django', r'import django', r'DJANGO_SETTINGS_MODULE'],
            'start_cmd': 'python manage.py runserver {port}',
            'default_port': 8000
        },
        'fastapi': {
            'files': ['main.py', 'app.py'],
            'patterns': [r'from fastapi import', r'FastAPI\(', r'@app\.(get|post|put|delete)'],
            'start_cmd': 'uvicorn main:app --host 0.0.0.0 --port {port}',
            'default_port': 8000
        },
        'nodejs': {
            'files': ['package.json', 'server.js', 'index.js', 'app.js'],
            'patterns': [r'express\(', r'require\(["\']express["\']\)', r'app\.listen'],
            'start_cmd': 'npm start',
            'default_port': 3000
        }
    }
    
    def __init__(self, backend_path: str):
        """
        Initialize detector with path to backend folder.
        
        Args:
            backend_path: Absolute path to backend directory
        """
        self.backend_path = Path(backend_path)
        if not self.backend_path.exists():
            raise ValueError(f"Backend path does not exist: {backend_path}")
    
    def detect_framework(self) -> Dict:
        """
        Detect backend framework and extract configuration.
        
        Returns:
            Dict containing framework detection results
        """
        results = {
            'framework': 'other',
            'confidence': 0.0,
            'detected_files': [],
            'suggested_start_command': '',
            'detected_apis': [],
            'detected_models': [],
            'port': 8000
        }
        
        # Check each framework
        for framework_name, signature in self.FRAMEWORK_SIGNATURES.items():
            confidence, found_files = self._check_framework_signature(signature)
            
            if confidence > results['confidence']:
                results['framework'] = framework_name
                results['confidence'] = confidence
                results['detected_files'] = found_files
                results['port'] = signature['default_port']
                results['suggested_start_command'] = signature['start_cmd'].format(
                    port=signature['default_port']
                )
        
        # Extract APIs and models based on detected framework
        if results['framework'] == 'django':
            results['detected_apis'] = self._extract_django_apis()
            results['detected_models'] = self._extract_django_models()
        elif results['framework'] == 'fastapi':
            results['detected_apis'] = self._extract_fastapi_apis()
            results['detected_models'] = self._extract_fastapi_models()
        elif results['framework'] == 'nodejs':
            results['detected_apis'] = self._extract_nodejs_apis()
            results['detected_models'] = self._extract_nodejs_models()
        
        return results
    
    def _check_framework_signature(self, signature: Dict) -> Tuple[float, List[str]]:
        """
        Check if framework signature matches files in backend path.
        
        Returns:
            Tuple of (confidence score 0-1, list of matching files)
        """
        found_files = []
        pattern_matches = 0
        total_checks = len(signature['files']) + len(signature['patterns'])
        
        # Check for signature files
        for filename in signature['files']:
            matching_files = list(self.backend_path.rglob(filename))
            if matching_files:
                found_files.extend([str(f.relative_to(self.backend_path)) for f in matching_files[:3]])
        
        # Check for code patterns in Python/JS files
        for pattern in signature['patterns']:
            if self._search_pattern_in_codebase(pattern):
                pattern_matches += 1
        
        # Calculate confidence score
        file_score = len(found_files) / max(len(signature['files']), 1)
        pattern_score = pattern_matches / max(len(signature['patterns']), 1)
        confidence = (file_score * 0.6 + pattern_score * 0.4)
        
        return confidence, found_files
    
    def _search_pattern_in_codebase(self, pattern: str) -> bool:
        """Search for regex pattern in Python/JS files"""
        extensions = ['.py', '.js', '.ts']
        
        for ext in extensions:
            for file_path in self.backend_path.rglob(f'*{ext}'):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if re.search(pattern, content):
                            return True
                except Exception:
                    continue
        return False
    
    def _extract_django_apis(self) -> List[Dict]:
        """Extract Django REST Framework API endpoints"""
        apis = []
        
        # Look for urls.py files
        for urls_file in self.backend_path.rglob('urls.py'):
            try:
                with open(urls_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find path() and re_path() patterns
                    patterns = re.findall(
                        r'path\(["\']([^"\']+)["\'].*?name=["\']([^"\']+)["\']',
                        content
                    )
                    
                    for path, name in patterns:
                        apis.append({
                            'path': f'/api/{path}',
                            'name': name,
                            'file': str(urls_file.relative_to(self.backend_path)),
                            'methods': ['GET', 'POST', 'PUT', 'DELETE']  # Assume REST methods
                        })
            except Exception:
                continue
        
        # Look for ViewSets and APIViews
        for view_file in self.backend_path.rglob('views.py'):
            apis.extend(self._extract_django_viewset_apis(view_file))
        
        return apis
    
    def _extract_django_viewset_apis(self, view_file: Path) -> List[Dict]:
        """Extract APIs from Django ViewSets"""
        apis = []
        
        try:
            with open(view_file, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a ViewSet or APIView
                        base_names = [base.id for base in node.bases if hasattr(base, 'id')]
                        
                        if any('ViewSet' in name or 'APIView' in name for name in base_names):
                            # Extract methods (get, post, put, delete, etc.)
                            methods = []
                            for item in node.body:
                                if isinstance(item, ast.FunctionDef):
                                    method_name = item.name.upper()
                                    if method_name in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                                        methods.append(method_name)
                            
                            if methods:
                                apis.append({
                                    'name': node.name,
                                    'file': str(view_file.relative_to(self.backend_path)),
                                    'methods': methods,
                                    'type': 'ViewSet' if 'ViewSet' in str(base_names) else 'APIView'
                                })
        except Exception:
            pass
        
        return apis
    
    def _extract_django_models(self) -> List[Dict]:
        """Extract Django models and their fields"""
        models = []
        
        for model_file in self.backend_path.rglob('models.py'):
            try:
                with open(model_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Check if inherits from models.Model
                            base_names = [self._get_full_name(base) for base in node.bases]
                            
                            if any('Model' in name for name in base_names):
                                fields = []
                                
                                # Extract field definitions
                                for item in node.body:
                                    if isinstance(item, ast.Assign):
                                        for target in item.targets:
                                            if isinstance(target, ast.Name):
                                                field_type = self._extract_field_type(item.value)
                                                if field_type:
                                                    fields.append({
                                                        'name': target.id,
                                                        'type': field_type
                                                    })
                                
                                if fields:
                                    models.append({
                                        'name': node.name,
                                        'file': str(model_file.relative_to(self.backend_path)),
                                        'fields': fields
                                    })
            except Exception:
                continue
        
        return models
    
    def _extract_fastapi_apis(self) -> List[Dict]:
        """Extract FastAPI endpoints"""
        apis = []
        
        for py_file in self.backend_path.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find decorator-based routes: @app.get("/path")
                    patterns = re.findall(
                        r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                        content
                    )
                    
                    for method, path in patterns:
                        apis.append({
                            'path': path,
                            'method': method.upper(),
                            'file': str(py_file.relative_to(self.backend_path))
                        })
            except Exception:
                continue
        
        return apis
    
    def _extract_fastapi_models(self) -> List[Dict]:
        """Extract Pydantic models from FastAPI"""
        models = []
        
        for py_file in self.backend_path.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Check if inherits from BaseModel
                            base_names = [self._get_full_name(base) for base in node.bases]
                            
                            if any('BaseModel' in name for name in base_names):
                                fields = []
                                
                                # Extract field annotations
                                for item in node.body:
                                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                        field_type = self._get_full_name(item.annotation)
                                        fields.append({
                                            'name': item.target.id,
                                            'type': field_type
                                        })
                                
                                if fields:
                                    models.append({
                                        'name': node.name,
                                        'file': str(py_file.relative_to(self.backend_path)),
                                        'fields': fields
                                    })
            except Exception:
                continue
        
        return models
    
    def _extract_nodejs_apis(self) -> List[Dict]:
        """Extract Express.js API endpoints"""
        apis = []
        
        for js_file in self.backend_path.rglob('*.js'):
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find Express routes: app.get('/path', ...)
                    patterns = re.findall(
                        r'(?:app|router)\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                        content
                    )
                    
                    for method, path in patterns:
                        apis.append({
                            'path': path,
                            'method': method.upper(),
                            'file': str(js_file.relative_to(self.backend_path))
                        })
            except Exception:
                continue
        
        return apis
    
    def _extract_nodejs_models(self) -> List[Dict]:
        """Extract Node.js/Mongoose models"""
        models = []
        
        for js_file in self.backend_path.rglob('*.js'):
            try:
                with open(js_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find Mongoose schema definitions
                    schema_pattern = r'new\s+(?:mongoose\.)?Schema\s*\(\s*\{([^}]+)\}'
                    matches = re.findall(schema_pattern, content, re.DOTALL)
                    
                    for match in matches:
                        fields = []
                        # Extract field definitions
                        field_patterns = re.findall(r'(\w+)\s*:\s*(\w+)', match)
                        
                        for field_name, field_type in field_patterns:
                            fields.append({
                                'name': field_name,
                                'type': field_type
                            })
                        
                        if fields:
                            models.append({
                                'name': js_file.stem,
                                'file': str(js_file.relative_to(self.backend_path)),
                                'fields': fields
                            })
            except Exception:
                continue
        
        return models
    
    @staticmethod
    def _get_full_name(node) -> str:
        """Get full name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{BackendDetector._get_full_name(node.value)}.{node.attr}"
        return str(node)
    
    @staticmethod
    def _extract_field_type(node) -> Optional[str]:
        """Extract Django field type from assignment"""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                return node.func.attr
            elif isinstance(node.func, ast.Name):
                return node.func.id
        return None
