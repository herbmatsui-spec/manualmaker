from setuptools import setup, find_packages

setup(
    name="manual_processor",
    version="2.1.0",
    description="Handwritten Manual Processor for Windows with Google Cloud AI",
    author="Developer",
    packages=find_packages(),
    install_requires=[
        "google-genai>=0.8.0",
        "google-cloud-vision>=3.7.0",
        "pypdfium2>=4.27.0",
        "pypdf>=4.0.0",
        "PyMuPDF>=1.24.0",
        "keyring>=24.0.0",
        "python-docx==1.1.0",
        "fpdf2>=2.7.0",
        "python-dotenv>=1.0.0",
        "pillow>=10.0.0",
        "edge-tts>=6.1.0",
        "gTTS>=2.5.0",
        "pydub>=0.25.1",
        "tenacity>=8.2.0",
        "mermaidx>=0.3.0",
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "python-multipart>=0.0.9",
        "jinja2>=3.1.0",
        "aiofiles>=24.1.0",
        "websockets>=12.0",
        "watchdog>=4.0.0",
        "pyinstaller>=6.0.0"
    ],
    entry_points={
        'console_scripts': [
            'manual-processor=main:main'
        ]
    },
    python_requires=">=3.8"
)