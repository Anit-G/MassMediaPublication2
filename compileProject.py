import subprocess
import tempfile
import os

def compile_project_to_temp(project_path):
    # Create a temporary file that persists after closing so we can read it
    # delete=False ensures the file stays on disk until we manually remove it
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_log:
        temp_name = temp_log.name
        
        print(f"Compiling {project_path}...")
        
        # Run the compileall module as a subprocess
        # -q: quiet mode (only errors)
        # -f: force compilation even if timestamps are up to date
        result = subprocess.run(
            [
                'python', '-m', 'compileall', 
                '-x', r'\.venv', # The regex to exclude any path containing .venv
                project_path
            ],
            stdout=temp_log,
            stderr=subprocess.STDOUT,
            text=True
        )
    
    print(f"Compilation finished. Results piped to: {temp_name}")
    return temp_name

# Usage
path_to_my_project = './'
log_file = compile_project_to_temp(path_to_my_project)

# Peek at the results
with open(log_file, 'r') as f:
    print("\n--- Log Content ---")
    print(f.read())