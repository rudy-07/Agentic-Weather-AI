import sys
import subprocess

def install_pypandoc():
    print("Installing pypandoc...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pypandoc"])

try:
    import pypandoc
except ImportError:
    install_pypandoc()
    import pypandoc

try:
    print("Downloading pandoc...")
    pypandoc.download_pandoc(version='3.1.12.2')
    print("Converting markdown to docx...")
    pypandoc.convert_file('hackathon_submission.md', 'docx', outputfile='Hackathon_Submission.docx')
    print("Successfully converted to Hackathon_Submission.docx")
except Exception as e:
    print(f"Error: {e}")
