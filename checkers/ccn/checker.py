"""
Cyclomatic Complexity Checker (CCN)

This checker uses the `lizard` tool to analyze cyclomatic complexity of functions
in Python files. It checks if all functions have complexity <= 20.

Usage in commit message: /checker:ccn
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional


def run_checker(
    commit_sha: str,
    files: Optional[List[str]],
    data_dir: Path,
    worktree_path: Optional[Path] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Execute cyclomatic complexity check using lizard.
    
    Args:
        commit_sha: Target commit SHA
        files: Optional list of files to check (None = all Python files in commit)
        data_dir: Repository data directory
        worktree_path: Optional path to git worktree checked out to commit_sha.
                      If provided, checker will analyze files from this worktree instead of data_dir.
                      This ensures checking the exact commit version of the code.
        
    Returns:
        {
            "success": bool,
            "score": float (0-100),
            "passed": int,
            "total": int,
            "details": List[dict],
            "message": str,
            "error": str (optional)
        }
    """
    threshold = 20  # Maximum allowed cyclomatic complexity
    
    try:
        # If worktree_path is provided, use it directly (this is the correct way - checking exact commit version)
        if worktree_path:
            worktree_path = Path(worktree_path)
            if not worktree_path.exists():
                return {
                    "success": False,
                    "score": 0.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": f"Worktree path does not exist: {worktree_path}",
                    "analysis": f"Worktree path does not exist: {worktree_path}",
                    "error": "worktree_not_found",
                }
            
            # Get Python files to check from worktree
            python_files = []
            
            if files:
                # Filter to only Python files and check if they exist in worktree
                python_files = [f for f in files if f.endswith('.py')]
            else:
                # Scan entire worktree for Python files
                for py_file in worktree_path.rglob("*.py"):
                    rel_path = py_file.relative_to(worktree_path)
                    python_files.append(str(rel_path).replace('\\', '/'))
            
            if not python_files:
                return {
                    "success": True,
                    "score": 100.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": f"No Python files found in commit {commit_sha[:8]} to check.",
                    "analysis": f"No Python files found in commit {commit_sha[:8]} to check.",
                }
            
            # Remove duplicates
            python_files = list(set(python_files))
            
            # Build file paths relative to worktree
            file_paths_to_check = []
            for file_path in python_files:
                file_path_obj = worktree_path / file_path
                if file_path_obj.exists():
                    file_paths_to_check.append(str(file_path_obj))
            
            if not file_paths_to_check:
                return {
                    "success": True,
                    "score": 100.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": f"No Python files found in worktree for commit {commit_sha[:8]}.",
                    "analysis": f"No Python files found in worktree for commit {commit_sha[:8]}.",
                }
        
        else:
            # Fallback to old logic (for backward compatibility or when git repo not available)
            # Get Python files to check
            python_files = []
            
            if files:
                # Filter to only Python files
                python_files = [f for f in files if f.endswith('.py')]
            else:
                # Load commit data to get all Python files
                commits_list_path = data_dir / "commits_list.json"
                if commits_list_path.exists():
                    with open(commits_list_path, 'r', encoding='utf-8') as f:
                        commits = json.load(f)
                    
                    # Find the commit
                    commit_data = None
                    for commit in commits:
                        sha = commit.get("sha") or commit.get("hash")
                        if sha == commit_sha:
                            commit_data = commit
                            break
                    
                    if commit_data:
                        # Get files from commit
                        commit_files = commit_data.get("files", [])
                        if isinstance(commit_files, list):
                            python_files = [
                                f.get("filename") if isinstance(f, dict) else f
                                for f in commit_files
                                if (f.get("filename") if isinstance(f, dict) else f).endswith('.py')
                            ]
                
                # Also check files directory for this commit
                commit_files_dir = data_dir / "commits" / commit_sha / "files"
                if commit_files_dir.exists():
                    for py_file in commit_files_dir.rglob("*.py"):
                        rel_path = py_file.relative_to(commit_files_dir)
                        python_files.append(str(rel_path).replace('\\', '/'))
            
            # If no Python files found from commit metadata, check entire repository (for forced checker or when commit has no Python changes)
            if not python_files:
                files_dir = data_dir / "files"
                if files_dir.exists():
                    # Check entire repository for Python files (current state)
                    for py_file in files_dir.rglob("*.py"):
                        rel_path = str(py_file.relative_to(files_dir)).replace('\\', '/')
                        python_files.append(rel_path)
                    if python_files:
                        print(f"[CCN Checker] No Python files in commit {commit_sha[:8]}, checking entire repository: found {len(python_files)} Python files")
            
            if not python_files:
                return {
                    "success": True,
                    "score": 100.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": "No Python files found in commit or repository to check.",
                    "analysis": "No Python files found in commit or repository to check.",
                }
            
            # Remove duplicates
            python_files = list(set(python_files))
            
            # Run lizard on files
            # We need to get actual file paths from data_dir
            file_paths_to_check = []
            files_dir = data_dir / "files"
            commits_files_dir = data_dir / "commits" / commit_sha / "files"
            
            for file_path in python_files:
                # Try files/ directory first (current state)
                file_path_obj = files_dir / file_path
                if file_path_obj.exists():
                    file_paths_to_check.append(str(file_path_obj))
                # Try commit-specific files directory
                elif commits_files_dir.exists():
                    commit_file_path = commits_files_dir / file_path
                    if commit_file_path.exists():
                        file_paths_to_check.append(str(commit_file_path))
            
            # If no files found but we have a files list, try scanning entire repository (for forced checker)
            if not file_paths_to_check and python_files:
                print(f"[CCN Checker] Files from commit metadata not found, scanning entire repository...")
                if files_dir.exists():
                    # Scan entire repository and match against requested files
                    repo_python_files = {}
                for py_file in files_dir.rglob("*.py"):
                    rel_path = str(py_file.relative_to(files_dir)).replace('\\', '/')
                    repo_python_files[rel_path] = str(py_file)
                
                # Match requested files with repository files
                for requested_file in python_files:
                    if requested_file in repo_python_files:
                        file_paths_to_check.append(repo_python_files[requested_file])
                    else:
                        # Try to find file by basename (in case path differs)
                        requested_basename = Path(requested_file).name
                        for repo_path, full_path in repo_python_files.items():
                            if Path(repo_path).name == requested_basename:
                                file_paths_to_check.append(full_path)
                                break
        
        # If still no files found, return error
        if not file_paths_to_check:
            if python_files:
                return {
                    "success": True,
                    "score": 100.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": f"Python files found in commit metadata ({len(python_files)} files) but file contents not available in data_dir.",
                    "analysis": f"Python files found in commit metadata ({len(python_files)} files) but file contents not available in data_dir. Files: {', '.join(python_files[:5])}{'...' if len(python_files) > 5 else ''}",
                }
            else:
                return {
                    "success": True,
                    "score": 100.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": "No Python files found in commit or repository to check.",
                    "analysis": "No Python files found in commit or repository to check.",
                }
        
        # Check if lizard is available (use Python API, not CLI)
        try:
            import lizard
        except ImportError:
            return {
                "success": False,
                "score": 0.0,
                "passed": 0,
                "total": 0,
                "details": [],
                "message": "lizard module not available. Please install: pip install lizard",
                "analysis": "lizard module not available. Please install: pip install lizard",
                "error": "lizard not found",
            }
        
        # Determine base directory for running lizard and path resolution
        if worktree_path:
            base_dir = worktree_path
            # When using worktree, use absolute paths
            file_paths_for_lizard = file_paths_to_check
        else:
            base_dir = data_dir
            file_paths_for_lizard = file_paths_to_check
        
        # Use lizard Python API instead of CLI (--json flag is not supported)
        try:
            # Analyze files using lizard Python API
            lizard_results = []
            for file_path in file_paths_for_lizard:
                try:
                    # lizard.analyze_file returns FileInformation object
                    file_info = lizard.analyze_file(str(file_path))
                    lizard_results.append(file_info)
                except Exception as e:
                    # Skip files that can't be analyzed
                    print(f"[CCN Checker] Warning: Failed to analyze {file_path}: {e}")
                    continue
            
            if not lizard_results:
                return {
                    "success": False,
                    "score": 0.0,
                    "passed": 0,
                    "total": 0,
                    "details": [],
                    "message": "No files could be analyzed by lizard",
                    "analysis": "No files could be analyzed by lizard",
                    "error": "no files analyzed",
                }
            
            # Convert lizard FileInformation objects to JSON-like structure
            lizard_data = []
            for file_info in lizard_results:
                file_data = {
                    "filename": file_info.filename,
                    "nloc": file_info.nloc,
                    "token_count": file_info.token_count,
                    "average_cyclomatic_complexity": file_info.average_cyclomatic_complexity,
                    "average_nloc": file_info.average_nloc,
                    "average_token_count": file_info.average_token_count,
                    "functions": []
                }
                
                for func in file_info.function_list:
                    func_data = {
                        "name": func.name,
                        "complexity": func.cyclomatic_complexity,
                        "nloc": func.nloc,
                        "token_count": func.token_count,
                        "parameters": func.parameters,
                        "start_line": func.start_line,
                        "end_line": func.end_line if hasattr(func, 'end_line') else func.start_line,
                    }
                    file_data["functions"].append(func_data)
                
                lizard_data.append(file_data)
            
            # Extract function complexity data
            all_functions = []
            failed_functions = []
            
            for file_data in lizard_data:
                file_path = file_data.get("filename", "")
                # Get relative path for cleaner display
                try:
                    file_path_obj = Path(file_path)
                    if base_dir and str(base_dir) in str(file_path):
                        rel_path = str(file_path_obj.relative_to(base_dir))
                    else:
                        rel_path = str(file_path_obj)
                except (ValueError, TypeError):
                    rel_path = file_path
                
                # Process functions from the new structure (file_data["functions"])
                for func_data in file_data.get("functions", []):
                    func_name = func_data.get("name", "unknown")
                    complexity = func_data.get("complexity", 0)
                    line_number = func_data.get("start_line", 0)
                    end_line = func_data.get("end_line", line_number)
                    nloc = func_data.get("nloc", 0)  # Lines of code
                    token_count = func_data.get("token_count", 0)
                    parameters = func_data.get("parameters", [])
                    
                    func_info = {
                        "file": rel_path,
                        "function": func_name,
                        "complexity": complexity,
                        "line": line_number,
                        "end_line": end_line,
                        "nloc": nloc,
                        "token_count": token_count,
                        "parameters": parameters,
                        "passed": complexity <= threshold,
                    }
                    
                    all_functions.append(func_info)
                    if complexity > threshold:
                        failed_functions.append(func_info)
            
            # Calculate statistics
            total = len(all_functions)
            passed = sum(1 for f in all_functions if f["passed"])
            score = (passed / total * 100) if total > 0 else 100.0
            
            # Build detailed analysis report
            analysis_report = []
            analysis_report.append(f"Cyclomatic Complexity Analysis Report (Threshold: {threshold})")
            analysis_report.append(f"Total functions analyzed: {total}")
            analysis_report.append(f"Passed: {passed}, Failed: {total - passed}")
            analysis_report.append("")
            
            if failed_functions:
                analysis_report.append(f"⚠️ Functions exceeding threshold ({len(failed_functions)}):")
                for func in failed_functions:
                    analysis_report.append(
                        f"  - {func['file']}:{func['line']} {func['function']}() "
                        f"(complexity={func['complexity']}, nloc={func['nloc']}, params={len(func['parameters'])})"
                    )
                analysis_report.append("")
            
            if total > 0:
                # Calculate average complexity
                avg_complexity = sum(f["complexity"] for f in all_functions) / total
                max_complexity = max(f["complexity"] for f in all_functions)
                analysis_report.append(f"Statistics:")
                analysis_report.append(f"  - Average complexity: {avg_complexity:.2f}")
                analysis_report.append(f"  - Maximum complexity: {max_complexity}")
                analysis_report.append(f"  - Functions with complexity > 15: {sum(1 for f in all_functions if f['complexity'] > 15)}")
                analysis_report.append(f"  - Functions with complexity > 10: {sum(1 for f in all_functions if f['complexity'] > 10)}")
                analysis_report.append("")
            
            # Detailed function list (grouped by file)
            analysis_report.append("Detailed Function Analysis:")
            current_file = None
            for func in sorted(all_functions, key=lambda x: (x["file"], x["line"])):
                if func["file"] != current_file:
                    current_file = func["file"]
                    analysis_report.append(f"\n{current_file}:")
                
                status = "✓" if func["passed"] else "✗"
                analysis_report.append(
                    f"  {status} Line {func['line']}: {func['function']}() "
                    f"- Complexity: {func['complexity']}, NLOC: {func['nloc']}"
                )
            
            analysis_text = "\n".join(analysis_report)
            
            # Build message
            if total == 0:
                message = "No functions found in Python files."
            elif passed == total:
                message = f"All {total} functions passed complexity check (threshold: {threshold})."
            else:
                failed = total - passed
                message = f"{passed}/{total} functions passed complexity check (threshold: {threshold}). {failed} functions exceeded threshold."
            
            return {
                "success": True,
                "score": round(score, 2),
                "passed": passed,
                "total": total,
                "details": all_functions,
                "message": message,
                "analysis": analysis_text,  # Detailed analysis report for LLM
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "score": 0.0,
                "passed": 0,
                "total": 0,
                "details": [],
                "message": "lizard execution timed out (>60s).",
                "analysis": "lizard execution timed out (>60s).",
                "error": "timeout",
            }
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse lizard output: {str(e)}"
            return {
                "success": False,
                "score": 0.0,
                "passed": 0,
                "total": 0,
                "details": [],
                "message": error_msg,
                "analysis": error_msg,
                "error": str(e),
            }
            
    except Exception as e:
        import traceback
        error_msg = f"Unexpected error: {str(e)}"
        return {
            "success": False,
            "score": 0.0,
            "passed": 0,
            "total": 0,
            "details": [],
            "message": error_msg,
            "analysis": error_msg,
            "error": traceback.format_exc(),
        }
