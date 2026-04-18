"""
Morning Market Brief — Quick Setup
====================================
Ejecuta este script para configurar todo automáticamente.

  python setup_brief.py
"""
import subprocess
import sys
import os
from pathlib import Path


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         LUIMOS MORNING BRIEF — SETUP v1.0                   ║
╚══════════════════════════════════════════════════════════════╝
""")

    project_dir = Path(__file__).parent

    # Step 1: Create virtual environment
    venv_dir = project_dir / "venv"
    if not venv_dir.exists():
        print("[1/4] Creando virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("  ✅ venv creado")
    else:
        print("[1/4] Virtual environment ya existe ✅")

    # Determine pip path
    if os.name == "nt":
        pip_path = venv_dir / "Scripts" / "pip.exe"
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"

    # Step 2: Install requirements
    print("[2/4] Instalando dependencias...")
    subprocess.run([str(pip_path), "install", "-r", str(project_dir / "requirements.txt")],
                   check=True, capture_output=True)
    print("  ✅ Dependencias instaladas")

    # Step 3: Create .env template
    env_file = project_dir / ".env"
    if not env_file.exists():
        print("[3/4] Creando archivo .env...")
        env_file.write_text("""# === LUIMOS MORNING BRIEF — CONFIGURACIÓN ===

# Anthropic API Key (requerido)
ANTHROPIC_API_KEY=sk-ant-XXXXXXXX

# Telegram Bot (opcional pero recomendado)
# 1. Habla con @BotFather → /newbot → copia el token
# 2. Envía un msg a tu bot, luego ve a:
#    https://api.telegram.org/bot<TOKEN>/getUpdates
#    y copia el chat_id del JSON
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID

# NewsAPI (opcional: para noticias del mercado)
# Regístrate en https://newsapi.org/register
NEWSAPI_KEY=
""", encoding="utf-8")
        print("  ✅ .env creado — EDITA ESTE ARCHIVO con tus API keys")
    else:
        print("[3/4] .env ya existe ✅")

    # Step 4: Create output directory
    output_dir = project_dir / "output"
    output_dir.mkdir(exist_ok=True)
    print("[4/4] Directorio output/ creado ✅")

    # Step 5: Create .gitignore
    gitignore = project_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("""venv/
output/
.env
__pycache__/
*.pyc
""", encoding="utf-8")

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ✅ SETUP COMPLETO                                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  PRÓXIMOS PASOS:                                             ║
║                                                              ║
║  1. Edita .env con tus API keys:                            ║
║     - ANTHROPIC_API_KEY (requerido)                          ║
║     - TELEGRAM_BOT_TOKEN + CHAT_ID (recomendado)            ║
║     - NEWSAPI_KEY (opcional)                                 ║
║                                                              ║
║  2. Activa el venv:                                          ║
║     Windows:  .\\venv\\Scripts\\activate                       ║
║     Linux:    source venv/bin/activate                       ║
║                                                              ║
║  3. Test rápido (sin Claude API):                           ║
║     python main.py --test                                    ║
║                                                              ║
║  4. Ejecutar brief completo:                                 ║
║     python main.py                                           ║
║                                                              ║
║  5. Programar ejecución diaria 9AM:                         ║
║     python main.py --setup                                   ║
║     (te da el comando de PowerShell para Task Scheduler)    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
