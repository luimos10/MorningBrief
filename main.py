"""
Morning Market Brief — Main Orchestrator
==========================================
Ejecuta el pipeline completo y maneja la programación diaria.

USO:
  python main.py              → Ejecuta el brief ahora (una vez)
  python main.py --schedule   → Programa ejecución diaria a las 9:00 AM
  python main.py --test       → Ejecuta sin Claude API (solo data + análisis)
"""
import sys
import time
import signal
import webbrowser
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import config
from data_fetcher import collect_all_data
from analysis import run_full_analysis
from brief_generator import generate_brief, markdown_to_plain
from html_renderer import brief_to_html
from telegram_delivery import deliver_to_telegram


def run_brief(open_browser: bool = True, send_telegram: bool = True) -> None:
    """Execute the full morning brief pipeline."""
    start_time = time.time()
    now = datetime.now()

    print("=" * 60)
    print(f"  📊 MORNING MARKET BRIEF — {now.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    try:
        # Step 1: Collect data
        print("\n[1/4] Recopilando datos del mercado...")
        market_data = collect_all_data()

        # Step 2: Run analysis
        print("\n[2/4] Ejecutando análisis técnico...")
        analysis = run_full_analysis(market_data)

        # Step 3: Generate brief with Claude API (single call, returns markdown)
        print("\n[3/4] Generando brief con Claude API...")
        brief_md = generate_brief(analysis)
        brief_text = markdown_to_plain(brief_md)

        # Step 4: Deliver
        print("\n[4/4] Entregando brief...")

        # Save HTML
        html_path = brief_to_html(brief_md)

        # Open in browser
        if open_browser:
            webbrowser.open(str(html_path))
            print(f"[OK] Brief abierto en el navegador")

        # Send to Telegram
        if send_telegram:
            deliver_to_telegram(brief_text, html_path)

        # Save plain text backup
        txt_path = config.HTML_OUTPUT_DIR / f"brief_{now.strftime('%Y-%m-%d')}.txt"
        txt_path.write_text(brief_text, encoding="utf-8")
        print(f"[OK] Backup texto guardado: {txt_path}")

        elapsed = time.time() - start_time
        print(f"\n{'=' * 60}")
        print(f"  ✅ Brief completado en {elapsed:.1f} segundos")
        print(f"  📁 HTML: {html_path}")
        print(f"  📁 TXT: {txt_path}")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n[ERROR] Error en el pipeline: {e}")
        import traceback
        traceback.print_exc()


def run_test() -> None:
    """Run data collection + analysis without Claude API (for testing)."""
    print("=" * 60)
    print("  🧪 TEST MODE — Solo datos + análisis (sin Claude API)")
    print("=" * 60)

    try:
        market_data = collect_all_data()
        analysis = run_full_analysis(market_data)

        # Print analysis summary
        print("\n" + "=" * 60)
        print("  RESUMEN DEL ANÁLISIS")
        print("=" * 60)

        for category in ["crypto", "indexes", "stocks", "commodities", "etfs"]:
            print(f"\n--- {category.upper()} ---")
            for asset in analysis.get(category, []):
                if "error" in asset:
                    print(f"  {asset['name']}: {asset['error']}")
                    continue
                print(f"  {asset['name']}: ${asset['price']:,.2f} ({asset['change_pct']:+.2f}%) "
                      f"| RSI: {asset['rsi']} | {asset['bias']}")
                print(f"    Estructura: {asset['structure']['structure']}")

        macro = analysis.get("macro", {})
        print(f"\n--- MACRO ---")
        fg = macro.get("fear_greed")
        if fg:
            print(f"  Fear & Greed: {fg['value']} ({fg['label']})")
        vix = macro.get("vix")
        if vix:
            print(f"  VIX: {vix}")
        dxy = macro.get("dxy")
        if dxy:
            print(f"  DXY: {dxy['value']} ({dxy['change']:+.2f}%)")

        print(f"\n✅ Test completado. Datos OK para generación del brief.")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


def schedule_daily():
    """
    Simple scheduler that runs the brief at the configured time daily.
    Uses a polling approach — for production, use Windows Task Scheduler.
    """
    target_hour = config.BRIEF_HOUR
    target_minute = config.BRIEF_MINUTE

    print(f"[SCHEDULER] Brief programado para las {target_hour:02d}:{target_minute:02d} diariamente")
    print(f"[SCHEDULER] Presiona Ctrl+C para detener\n")

    # Handle graceful shutdown
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        print("\n[SCHEDULER] Detenido por el usuario.")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    last_run_date = None

    while running:
        now = datetime.now()
        today = now.date()

        # Check if it's time to run
        if (now.hour == target_hour and
            now.minute >= target_minute and
            last_run_date != today):

            print(f"\n[SCHEDULER] ¡Es hora! Ejecutando brief...")
            run_brief(open_browser=True, send_telegram=True)
            last_run_date = today
            print(f"[SCHEDULER] Próxima ejecución: mañana a las {target_hour:02d}:{target_minute:02d}")

        time.sleep(30)  # Check every 30 seconds


def setup_windows_task():
    """Print instructions for setting up Windows Task Scheduler."""
    python_path = sys.executable
    script_path = Path(__file__).resolve()

    print("""
╔══════════════════════════════════════════════════════════════╗
║  CONFIGURAR WINDOWS TASK SCHEDULER                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Opción A: Comando PowerShell (recomendado)                 ║
║  Ejecuta esto en PowerShell como Administrador:             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    ps_command = f"""
$action = New-ScheduledTaskAction `
    -Execute '{python_path}' `
    -Argument '"{script_path}"' `
    -WorkingDirectory '{script_path.parent}'

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At '{config.BRIEF_HOUR:02d}:{config.BRIEF_MINUTE:02d}'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries

Register-ScheduledTask `
    -TaskName 'MorningMarketBrief' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Luimos Morning Market Brief - Daily at 9AM'
"""
    print(ps_command)

    print("""
╔══════════════════════════════════════════════════════════════╗
║  Opción B: Manual via Task Scheduler GUI                    ║
╠══════════════════════════════════════════════════════════════╣
║  1. Abre Task Scheduler (busca en Start)                    ║
║  2. Create Basic Task → 'MorningMarketBrief'                ║
║  3. Trigger: Daily, 09:00 AM                                ║
║  4. Action: Start a Program                                 ║
║     Program: """ + str(python_path) + """
║     Arguments: """ + f'"{script_path}"' + """
║     Start in: """ + str(script_path.parent) + """
║  5. ✅ Finish                                               ║
╚══════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(
        description="Luimos Morning Market Brief",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py              Ejecuta el brief ahora
  python main.py --schedule   Programa ejecución diaria
  python main.py --test       Test sin Claude API
  python main.py --setup      Muestra config para Task Scheduler
  python main.py --no-telegram  Sin enviar a Telegram
  python main.py --no-browser   Sin abrir en el navegador
        """
    )
    parser.add_argument("--schedule", action="store_true", help="Ejecutar en modo scheduler")
    parser.add_argument("--test", action="store_true", help="Modo test (sin Claude API)")
    parser.add_argument("--setup", action="store_true", help="Mostrar setup Task Scheduler")
    parser.add_argument("--no-telegram", action="store_true", help="No enviar a Telegram")
    parser.add_argument("--no-browser", action="store_true", help="No abrir browser")

    args = parser.parse_args()

    if args.setup:
        setup_windows_task()
    elif args.test:
        run_test()
    elif args.schedule:
        schedule_daily()
    else:
        run_brief(
            open_browser=not args.no_browser,
            send_telegram=not args.no_telegram,
        )


if __name__ == "__main__":
    main()
