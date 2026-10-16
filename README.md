<p align="center">
  <img src="docs/images/banner.svg" alt="Universal Web Scraper: teach a browser task once and get a Python bot that repeats it" width="100%">
</p>

<p align="center">
  <a href="https://github.com/MatPasquali/universal-web-scraper/actions/workflows/tests.yml"><img src="https://github.com/MatPasquali/universal-web-scraper/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-3.14-3776AB?logo=python&logoColor=white" alt="Python 3.14">
  <img src="https://img.shields.io/badge/Playwright-1.61-2EAD33?logo=playwright&logoColor=white" alt="Playwright 1.61">
  <img src="https://img.shields.io/badge/Windows-Microsoft%20Edge-0078D4?logo=microsoftedge&logoColor=white" alt="Windows and Microsoft Edge">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT license"></a>
</p>

<p align="center"><b>English</b> · <a href="README.pt-BR.md">Português (Brasil)</a></p>

Universal Web Scraper turns a task you do by hand in a web system into a standalone Python bot. You open an empty Microsoft Edge window, sign in, click through the screens, download the file and close the window. The tool reads what Playwright recorded, asks which typed values are credentials and where each download should go, and writes `bots/<name>.py`. Run that file whenever you need the data, or let Windows Task Scheduler run it with `--headless`.

<p align="center">
  <img src="docs/images/bot-run.gif" alt="A generated bot signing in, filtering by SP and exporting a CSV in the demo system" width="820">
</p>

## Why it exists

A lot of office work is the same routine: log in to an internal system, pick a location, apply a filter, wait for the table, export a CSV and move it from Downloads to another folder. Playwright's recorder already captures those clicks, using selectors based on roles, labels and visible text. A raw recording still makes a poor bot. It keeps your password in plain text, clicks Export before the filter has finished loading, cancels the confirmation dialog you accepted, and never saves the downloaded file anywhere you can find it. This project closes those gaps so a recording becomes something you can schedule.

## How it works

<p align="center">
  <img src="docs/images/how-it-works.svg" alt="Record in Edge, analyze the recording, answer a few questions, generate the bot, run it" width="100%">
</p>

1. `gravador.py` runs `python -m playwright codegen --channel msedge` and waits until you close the browser. The raw script contains your password, so it only lives in a temporary folder that is deleted right after it is read.
2. `analisador.py` parses the script with Python's `ast` module. It drops the browser setup, collects every typed value and every download, and flags any `page.goto()` that came right after an action on the same page.
3. `interface.py` asks, in the terminal, which fields are credentials, which folder each download goes to, and whether you typed each flagged address yourself.
4. `gerador_bot.py` rewrites the steps and fills `modelo_bot.py.tpl`. The result has to pass `compile()` and must not contain any credential value, otherwise nothing is saved.
5. You run `bots/<name>.py`.

## Quick start

You need Windows, Microsoft Edge and Python (tested on 3.14). Playwright drives the Edge that is already installed, so there is no browser to download.

```powershell
git clone https://github.com/MatPasquali/universal-web-scraper.git
cd universal-web-scraper
pip install -r requirements.txt
python webscraper_universal.py
```

The command-line prompts, code comments and identifiers are in Brazilian Portuguese. The session is short, and this is all of it:

<p align="center">
  <img src="docs/images/teaching-session.svg" alt="Terminal session: naming the bot, choosing credentials and the download folder" width="820">
</p>

## Try it on the demo system

The repository ships a small fake quotation system that the tests also use. It has a login, a filter that takes 1.5 seconds to load, an export button that is never disabled, a confirmation dialog, a search box that filters as you type, a pop-up picker that closes itself and an export that opens in a new window.

```powershell
python tests/site_demo/servidor.py    # http://127.0.0.1:8000, user demo, password demo123
```

In a second terminal run `python webscraper_universal.py`. In the empty Edge window open `127.0.0.1:8000`, sign in, choose SP, click Filtrar, click Exportar CSV, accept the confirmation and close the window.

<p align="center">
  <img src="docs/images/demo-dashboard.png" alt="Demo quotation system filtered by SP" width="820">
</p>

## What a generated bot looks like

Each bot is a single file that only depends on `playwright` and `python-dotenv`. These are the steps of the bot generated from the session above, with the log lines left out:

```python
def executar_passos(context: BrowserContext) -> None:
    page = context.new_page()
    page.goto('http://127.0.0.1:8000/')
    aguardar_rede(page)
    page.get_by_label('Usuário').click()
    aguardar_rede(page)
    page.get_by_label('Usuário').fill(credencial('COTACAO_SP_USUARIO'))
    aguardar_rede(page)
    page.get_by_label('Senha').click()
    aguardar_rede(page)
    page.get_by_label('Senha').fill(credencial('COTACAO_SP_SENHA'))
    aguardar_rede(page)
    page.get_by_role('button', name='Entrar').click()
    aguardar_rede(page)
    page.get_by_label('Local').select_option('SP')
    aguardar_rede(page)
    page.get_by_role('button', name='Filtrar').click()
    aguardar_rede(page)
    page.once('dialog', lambda dialog: dialog.accept())
    aguardar_rede(page)
    with page.expect_download() as download_info:
        page.get_by_role('button', name='Exportar CSV').click()
    download = download_info.value
    salvar_download(download, DESTINO_DOWNLOAD_1)
```

The template around those steps reads the credentials from `.env` and stops with exit code 2, before opening the browser, if one is missing. It writes every step to `logs/<name>.log` with credential values replaced by `***`. When a step fails it saves a screenshot of each open page to `logs/` and exits with code 1. Downloads that the recording did not capture go to `downloads/<name>/`, with a warning in the log. `TIMEOUT_MS`, `ESPERA_REDE_MS` and the download folders are constants at the top of the file.

## Scheduling

In Windows Task Scheduler, choose *Create Basic Task*, pick a trigger, then *Start a program*:

| Field | Value |
|---|---|
| Program/script | the `python.exe` shown in the bot's header |
| Add arguments | `"C:\path\to\universal-web-scraper\bots\my_bot.py" --headless` |
| Start in | the project folder |

*Last Run Result* shows the exit code: `0x0` worked, `0x1` a step failed (see the log and screenshot in `logs/`), `0x2` a credential is missing from `.env`.

A few things to know before scheduling:

- With *Run whether user is logged on or not*, mapped drives such as `Z:\` do not exist. Use a network path (`\\server\share`) as the download folder.
- The bot replays exactly what was typed during the recording. A date typed into a filter stays the same date every day; edit that step in the bot if it has to change.
- If your password changes, update `.env` or teach the bot again. With the old password the bot fails at login, and some systems lock the account after a few failed attempts.

## Design notes

Each of these came from a bug found while building or testing the project, and each one has a test.

### Waiting for data that loads in the background

`wait_for_load_state("networkidle")` only applies to navigations, so after a filter that fetches data with XHR it returns immediately. `aguardar_rede()` counts in-flight requests through the context's `request`, `requestfinished` and `requestfailed` events and waits until the network has been quiet for 500 ms, up to `ESPERA_REDE_MS`. It runs after every click and every typed value, and before every download. If the page it was given closes, as a picker pop-up does, it keeps waiting through another open window, and requests from closed windows stop counting. When the limit is reached it logs a line and moves on. One test removes these waits and checks that the exported CSV comes out wrong.

### Confirmation dialogs

Playwright's recorder writes `dialog.dismiss()` for every dialog, because the event it records does not say whether you clicked OK or Cancel. The generated bot calls `dialog.accept()`. With `dismiss()` the demo export never starts and the bot times out waiting for the download.

### Pages that reload themselves

Older stacks such as ASP.NET WebForms and JSF reload the page after you tick a box or pick an item from a list. Codegen records that reload as `page.goto(url)`, and replaying it opens the page from scratch and loses the filter. When a recording navigates right after an action on the same page, the tool asks whether you typed that address. If you did not, the bot waits for the reload instead of navigating.

### Downloads that start in a new window

When a file comes from a window that has just opened, codegen does not attach the download to any action and the recording loses it. The bot listens for downloads on every page and saves the ones the recording missed.

### Credentials and `.env`

`set_key` from python-dotenv only escapes single quotes. A value ending in a backslash corrupts the next line of the file, and `\\` turns into `\`. Each value is written in the form the parser reads back unchanged, and the tool reads the file again to confirm it. Bots load `.env` with `interpolate=False`, so a `$` in a password stays a `$`.

### Secrets in logs

When a `fill()` fails, Playwright's error message repeats the text that was being typed. The bot's log formatter replaces every credential value with `***`, longest value first, because a user name can be part of a password.

### Ctrl+C during a recording

`python -m playwright` is a thin wrapper around a Node.js process, and Node starts Edge. Killing only the wrapper leaves Node and the browser running, so the recorder ends the whole process tree with `taskkill /T`.

## Security

- `.env`, `bots/`, `logs/` and `downloads/` are listed in `.gitignore`. Bots contain internal addresses and field names, and logs can contain screenshots.
- Values you mark as credentials never appear in the generated code, in the logs or on screen. For a password, the terminal only shows its length.
- Only the fields you mark go to `.env`. A password typed into a field with an unusual label (a PIN, an access code) is not pre-selected, so read the list before pressing Enter.
- If you make a mistake while recording, close Edge and start over. The recorder keeps every attempt, including a mistyped password, and the bot would repeat them.

## Limitations

- Logins with MFA or SSO prompts and CAPTCHAs cannot be replayed.
- The bot repeats actions and downloads files. It does not extract data from the page.
- For file uploads, codegen records only the file name, not its path.
- It runs on Windows only (Task Scheduler, `taskkill`), and Playwright is pinned to 1.61.0 because the parser depends on the format of the code that codegen writes.

## Tests

```powershell
pytest -q
```

There are 97 tests. 89 run offline. The other 8 generate a bot from a recording and run it in headless Edge against the demo system, covering a slow filter, a search that filters as you type, a pop-up that closes itself, a download from a new window, a confirmation before export, and a password that has to stay out of the log when a step fails. GitHub Actions runs the whole suite on `windows-latest`. The end-to-end tests are skipped on machines without Edge.

## Project layout

```text
webscraper_universal.py   entry point: teach, generate, teach another
gravador.py               runs codegen in Edge
analisador.py             parses the recording with ast
interface.py              terminal prompts and the folder picker
credenciais.py            variable names and .env writing
gerador_bot.py            rewrites the steps and fills the template
modelo_bot.py.tpl         template for every generated bot
tests/                    tests, sample recordings and the demo system
docs/images/              images used in this README
```

## License

MIT. See [LICENSE](LICENSE).
