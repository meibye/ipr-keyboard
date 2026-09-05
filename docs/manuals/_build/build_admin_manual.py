"""Build the Danish administrator manual (Administratormanual) as a Word document."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from docx_helpers import Manual

OUT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_SCRIPT = REPO_ROOT / "scripts" / "deploy" / "make_payload.sh"
VERSION = "1.3"
DATE = "5. september 2026"

# Danish rationale for each payload entry.  The entries themselves come from
# make_payload.sh — this maps them to manual prose.  The keys are checked
# against the script's list at build time, so adding or removing an entry there
# fails this build until the text is written.
PAYLOAD_REASONS = {
    "src": "Selve pakken, inklusive web/templates og web/static.",
    "provision": "Provisioneringstrin 00–07.",
    "scripts": "Udrulnings-, tjeneste-, BLE- og headless-skripts.",
    "pyproject.toml": "Kræves af uv pip install -e .",
    "README.md": "pyproject.toml angiver readme = \"README.md\". Mangler filen, fejler "
                 "den editerbare installation.",
    "config.default.json": "Læses ved kørsel af utils/helpers.py som udgangspunkt for "
                           "konfigurationen.",
    "users.default.json": "Læses ved kørsel af web/auth.py som udgangspunkt for "
                          "brugerdatabasen.",
    "uv.lock": "Valgfri. Kun nødvendig, hvis der køres uv sync på enheden.",
    "tests": "Kun med ved --with-tests. Lader udviklingsenheden køre testsuiten.",
}


def payload_entries() -> list[str]:
    """Return the payload file list from make_payload.sh, in script order.

    Prefers running the script, so the manual reflects exactly what a deploy
    would pack.  Falls back to parsing the PAYLOAD array when bash is not
    available — the manual must remain buildable on a machine without it.
    """
    try:
        out = subprocess.run(
            ["bash", str(PAYLOAD_SCRIPT), "--list"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout
        entries = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if entries:
            return entries
    except (OSError, subprocess.SubprocessError):
        pass

    text = PAYLOAD_SCRIPT.read_text(encoding="utf-8")
    block = re.search(r"^PAYLOAD=\((.*?)^\)", text, re.S | re.M)
    if not block:
        raise SystemExit(f"Cannot read PAYLOAD list from {PAYLOAD_SCRIPT}")
    # Strip trailing comments first: they quote filenames too, and matching
    # inside them yields phantom duplicate entries.
    body = re.sub(r"#.*$", "", block.group(1), flags=re.M)
    return re.findall(r'"([^"]+)"', body)


def payload_rows() -> list[list[str]]:
    """Table rows for the payload list, generated from the deploy script."""
    entries = payload_entries()
    missing = [e for e in entries if e not in PAYLOAD_REASONS]
    if missing:
        raise SystemExit(
            "make_payload.sh lists entries with no Danish description in "
            f"PAYLOAD_REASONS: {', '.join(missing)}. Add them to "
            f"{Path(__file__).name} and rebuild."
        )
    # Directories are shown with a trailing slash, matching the manual's style.
    return [
        [e + "/" if (REPO_ROOT / e).is_dir() else e, PAYLOAD_REASONS[e]]
        for e in entries
    ]


def build() -> None:
    m = Manual(
        title="Administratormanual",
        subtitle="IPR Pen Bridge — opsætning, konfiguration, drift og fejlfinding",
        doc_id="IPR-DOC-002",
        version=VERSION,
        date=DATE,
    )
    m.toc()

    # ---------------------------------------------------------------- 1
    m.h1("1. Om denne manual")
    m.rich([
        ("Denne manual henvender sig til den, der installerer, konfigurerer, opdaterer og "
         "fejlsøger IPR Pen Bridge. Den forudsætter praktisk erfaring med Linux, systemd og "
         "netværk. Slutbrugerens vejledning findes i dokumentet ", ""),
        ("Brugermanual (IPR-DOC-001)", "b"),
        (".", ""),
    ])

    m.h2("1.1 Forudsætninger")
    m.bullets([
        "Raspberry Pi Zero 2 W (eller Pi 4 til udvikling og test) med Raspberry Pi OS Lite, "
        "Bookworm, 64-bit.",
        "SSH-adgang eller tastatur/skærm til førstegangsopsætningen.",
        "IRIS-skanner, som eksponerer sine skanninger som tekstfiler over USB "
        "(masselager eller MTP).",
        "En vært med Bluetooth Low Energy — typisk en Windows-PC.",
        "Kendskab til systemd, journalctl, nmcli og bash.",
    ])

    m.h2("1.2 Terminologi i denne manual")
    m.table(
        ["Begreb", "Betydning"],
        [
            ["Enheden", "Raspberry Pi'en med IPR Pen Bridge-softwaren installeret."],
            ["Værten", "Den PC, enheden er parret med, og som modtager tastetryk."],
            ["Dashboard", "Hovedgrænsefladen på https://<værtsnavn>.local/ — daglig drift."],
            ["Setup-UI", "Nødgrænsefladen på https://10.42.0.1/setup/ — tilgængelig over "
                         "opsætningshotspottet, også uden netværk."],
            ["Hotspot", "Enhedens eget Wi-Fi-adgangspunkt på wlan0, styret af "
                        "ipr-provision.service."],
        ],
        widths=[3.6, 12.0],
        caption="Begreber brugt gennemgående i manualen.",
    )

    m.note("Kildekode og skripts, der refereres i manualen, ligger i projektets git-repository. "
           "Stier angives relativt til repositoriets rod, medmindre andet er nævnt.", "info")

    # ---------------------------------------------------------------- 2
    m.h1("2. Systemarkitektur", new_page=True)

    m.h2("2.1 Formål og overordnet virkemåde")
    m.p("IPR Pen Bridge omsætter tekstfiler produceret af en IRIS-skanner til HID-tastetryk "
        "på en Bluetooth-forbundet vært. Enheden overvåger en eller flere mapper, læser nye "
        "filer, sender indholdet gennem en navngiven pipe til en BLE HID-dæmon og sletter "
        "filen bagefter. Parallelt hermed serverer den et lokalt webdashboard til status, "
        "hændelser, konfiguration og strømstyring.")

    m.figure("fig07_arkitektur.png",
             "Komponenter, tjenester og datavej. Skanneren leverer filer over USB; "
             "teksten sendes gennem FIFO'en til BLE-laget og videre til værten.")

    m.h2("2.2 Dataveje")
    m.code(
        "IrisPen-mappe (config.json → IrisPenFolders)\n"
        "  → src/ipr_keyboard/usb/detector.py      opdager nyeste fil pr. mappe\n"
        "  → src/ipr_keyboard/usb/reader.py        læser indhold, respekterer MaxFileSize\n"
        "  → src/ipr_keyboard/bluetooth/keyboard.py send_text(), timeout 30 s\n"
        "  → /usr/local/bin/bt_kb_send             skalhjælper\n"
        "  → /run/ipr_bt_keyboard_fifo             navngiven pipe\n"
        "  → bt_hid_ble.service                    HID over GATT\n"
        "  → BlueZ/hci0 → værten modtager tastetryk"
    )

    m.h2("2.3 Tjenester")
    m.table(
        ["Systemd-enhed", "Ansvar", "Kører som"],
        [
            ["ipr_keyboard.service",
             "Hovedapplikationen: filovervågning, webserver, GPIO-overvågning.",
             "applikationsbruger"],
            ["bt_hid_ble.service",
             "BLE HID over GATT-dæmon. Læser FIFO'en og udsender HID-rapporter.",
             "root"],
            ["bt_hid_agent_unified.service",
             "BlueZ Agent1: parring og autorisation. Standard: NoInputNoOutput.",
             "root"],
            ["ipr-provision.service",
             "Opsætningshotspot på wlan0 (10.42.0.1). Type=oneshot, RemainAfterExit=yes.",
             "root"],
            ["ipr-cert-renew.timer",
             "Årlig fornyelse af servercertifikatet. CA-nøglen bevares.",
             "root"],
        ],
        widths=[4.6, 8.6, 2.4],
        mono_cols=(0,),
        caption="Systemd-enheder installeret af provisioneringen.",
    )

    m.note("Enhederne bt_hid_uinput.service, ipr_backend_manager.service og "
           "bt_hid_daemon.service optræder i ældre skripts og dokumentation, men leveres "
           "ikke i den nuværende kodebase. Findes de på en enhed, stammer de fra en tidligere "
           "installation og bør fjernes.", "warn")

    m.h2("2.4 Installerede filer på enheden")
    m.table(
        ["Sti", "Indhold"],
        [
            ["/usr/local/bin/bt_kb_send", "Skalhjælper, der skriver tekst til FIFO'en."],
            ["/usr/local/bin/bt_hid_ble_daemon.py", "BLE HID-dæmonen."],
            ["/usr/local/bin/bt_hid_agent_unified.py", "BlueZ-parringsagenten."],
            ["/usr/local/sbin/ipr-provision.sh", "Hotspot-skriptet."],
            ["/run/ipr_bt_keyboard_fifo", "Navngiven pipe mellem app og BLE-dæmon."],
            ["/etc/ipr-ssl/", "CA og servercertifikat samt private nøgler."],
            ["/etc/ipr-hotspot.secret", "SSID og adgangskode til hotspot (tilstand 0600)."],
            ["/opt/ipr_common.env", "Miljøvariable for provisionering og skripts."],
            ["/opt/ipr_state/", "Tilstands- og verifikationsoutput fra provisioneringen."],
            ["/var/lib/ipr-keyboard/boot-count", "Tæller for tredobbelt tænd/sluk-udløser."],
        ],
        widths=[6.6, 9.0],
        mono_cols=(0,),
        caption="Vigtige stier på en provisioneret enhed.",
    )

    # ---------------------------------------------------------------- 3
    m.h1("3. Førstegangsopsætning", new_page=True)

    m.figure("fig08_provisionering.png",
             "Provisioneringsforløbet i syv trin med genstartspunkter efter trin 01 og 02.")

    m.h2("3.1 Klargør microSD-kortet med Raspberry Pi Imager")
    m.p("Enheden starter fra et microSD-kort, der skrives med Raspberry Pi Imager på "
        "administratorens PC. Imageren kan samtidig forudkonfigurere værtsnavn, konto, "
        "Wi-Fi og SSH, så enheden er tilgængelig over netværket ved første opstart. Det "
        "sparer et skridt med tastatur og skærm og er den anbefalede fremgangsmåde.")

    m.p("Vælg styresystem", bold=True)
    m.bullets([
        "Under Raspberry Pi-enhed vælges den model, kortet skal bruges i.",
        "Under Styresystem vælges Raspberry Pi OS (other) og derefter "
        "Raspberry Pi OS Lite (64-bit).",
        "Under Lagerplads vælges microSD-kortet. Kontrollér valget — kortet overskrives "
        "uden yderligere advarsel.",
    ], numbered=True)
    m.note("Det skal være Lite-udgaven uden skrivebordsmiljø og 64-bit. Zero 2 W har 512 MB "
           "RAM, og et skrivebordsmiljø efterlader ikke ressourcer nok til BLE-stakken og "
           "webserveren. 64-bit kræves, fordi projektets Python-afhængigheder installeres "
           "som aarch64-pakker.", "warn")

    m.p("Udfyld de avancerede indstillinger", bold=True)
    m.p("Vælg Rediger indstillinger, når Imageren spørger, om indstillingerne skal "
        "tilpasses. Udfyld begge faneblade som vist herunder, før der skrives.")
    m.table(
        ["Indstilling", "Værdi", "Bemærkning"],
        [
            ["Værtsnavn", "ipr-prod-zero2 eller ipr-dev-pi4",
             "Produktionsenhed henholdsvis udviklingsenhed. Skal være identisk med HOSTNAME "
             "i /opt/ipr_common.env."],
            ["Brugernavn", "meibye",
             "Applikations- og administrationskontoen. Alle stier i manualen tager "
             "udgangspunkt i denne bruger."],
            ["Adgangskode", "(den aftalte adgangskode)",
             "Angives ikke i manualen. Se organisationens adgangskodeopbevaring."],
            ["Konfigurér trådløst LAN", "SSID: DPbUFEKqA",
             "Hjemmenettet. Adgangskoden er den aftalte og angives ikke her."],
            ["Land for trådløst LAN", "DK",
             "Skal sættes. Uden landekode blokeres wlan0 af rfkill, og enheden kommer "
             "ikke på nettet."],
            ["Aktivér SSH", "Ja — brug adgangskodegodkendelse",
             "Giver den første adgang. Nøglebaseret adgang lægges på bagefter, se afsnit 3.2."],
            ["Raspberry Pi Connect", "Deaktiveret",
             "Enheden må ikke kunne fjernbetjenes via Raspberry Pi's skytjeneste."],
        ],
        widths=[3.4, 4.6, 7.6],
        caption="Værdier i Raspberry Pi Imagers avancerede indstillinger.",
    )

    m.note("Adgangskoder er bevidst udeladt af manualen. Både kontoens adgangskode og "
           "Wi-Fi-adgangskoden er kendte værdier, som administratoren henter fra "
           "organisationens sædvanlige opbevaring — de må ikke skrives ind i dette "
           "dokument eller i repositoriet.", "danger")

    m.note("Adgangskodegodkendelse er valgt her, fordi der endnu ikke ligger en offentlig "
           "nøgle på enheden. Læg en nøgle på ved første forbindelse som beskrevet i "
           "afsnit 3.2, og overvej derefter at slå adgangskodegodkendelse fra i "
           "/etc/ssh/sshd_config på produktionsenheden.", "tip")

    m.p("Skriv og start op", bold=True)
    m.bullets([
        "Vælg Skriv, og bekræft. Imageren skriver og verificerer kortet.",
        "Sæt kortet i enheden, og tilslut strøm.",
        "Den første opstart tager typisk to til tre minutter, fordi filsystemet udvides "
        "og Wi-Fi konfigureres.",
        "Kontrollér at enheden er kommet på nettet.",
    ], numbered=True)
    m.code(
        "ping ipr-prod-zero2.local\n"
        "ssh meibye@ipr-prod-zero2.local     # adgangskode fra Imager-opsætningen"
    )
    m.p("Svarer enheden ikke, så kontrollér SSID og Wi-Fi-adgangskode ved at sætte kortet "
        "i PC'en igen og gennemse firstrun-filerne på boot-partitionen. Alternativt "
        "tilsluttes tastatur og skærm direkte.")

    m.note("Imagerens værtsnavn gælder fra første opstart, men trin 02 sætter det "
           "autoritativt ud fra HOSTNAME i /opt/ipr_common.env. Afviger de to værdier, "
           "skifter enhedens navn midt i provisioneringen, og den igangværende "
           "SSH-forbindelse mister sit navneopslag. Hold værdierne ens.", "warn")

    m.h2("3.2 SSH-adgang til enheden")
    m.p("Al provisionering, udrulning og fejlsøgning foregår over SSH. Enheden skal derfor "
        "kunne nås fra administratorens PC, før noget andet kan lade sig gøre.")

    m.p("Aktivér SSH på SD-kortet", bold=True)
    m.p("SSH er slået fra som standard i Raspberry Pi OS Lite. Slå det til på én af to måder, "
        "mens SD-kortet stadig sidder i PC'en:")
    m.bullets([
        "I Raspberry Pi Imager: åbn de avancerede indstillinger før skrivning, sæt hak i "
        "Aktivér SSH, vælg godkendelse med offentlig nøgle, og angiv brugernavn og værtsnavn.",
        "Manuelt: opret en tom fil ved navn ssh — uden filendelse — i rodmappen på "
        "boot-partitionen. Partitionen er FAT32 og kan skrives fra enhver PC.",
    ])

    m.p("Værtsnavne og konti", bold=True)
    m.table(
        ["Enhed", "Værtsnavn", "Konto", "Anvendelse"],
        [
            ["Produktionsenhed (Zero 2 W)", "ipr-prod-zero2", "meibye",
             "Provisionering, udrulning og drift."],
            ["Udviklingsenhed (Pi 4)", "ipr-dev-pi4", "meibye",
             "Udvikling og test."],
            ["Begge", "(samme)", "copilotdiag",
             "Afgrænset fejlsøgning. Oprettes af trin 05 og bruger sin egen nøgle."],
        ],
        widths=[4.2, 3.4, 2.8, 5.2],
        mono_cols=(1, 2),
        caption="Værtsnavne og SSH-konti. Værtsnavnet sættes af trin 02 ud fra HOSTNAME i "
                "/opt/ipr_common.env og gør enheden tilgængelig som <værtsnavn>.local.",
    )

    m.p("Opret en nøgle og læg den på enheden", bold=True)
    m.p("Adgang med offentlig nøgle er mere robust end adgangskode og er en forudsætning "
        "for de scriptede udrulninger. Kør på administratorens PC:")
    m.code(
        "ssh-keygen -t ed25519 -C \"admin@ipr\" -f ~/.ssh/ipr_rpi\n"
        "\n"
        "# Linux og macOS — kopiér nøglen til enheden\n"
        "ssh-copy-id -i ~/.ssh/ipr_rpi.pub meibye@ipr-prod-zero2.local\n"
        "\n"
        "# Windows PowerShell — ssh-copy-id findes ikke; brug i stedet\n"
        "Get-Content $env:USERPROFILE\\.ssh\\ipr_rpi.pub |\n"
        "  ssh meibye@ipr-prod-zero2.local \"mkdir -p ~/.ssh && chmod 700 ~/.ssh &&\n"
        "  cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\""
    )

    m.p("Forbind til enheden", bold=True)
    m.code(
        "# Over hjemmenettet, via mDNS\n"
        "ssh -i ~/.ssh/ipr_rpi meibye@ipr-prod-zero2.local\n"
        "\n"
        "# Over opsætningshotspottet — fast adresse, virker uden netværk\n"
        "ssh -i ~/.ssh/ipr_rpi meibye@10.42.0.1\n"
        "\n"
        "# Fejlsøgningskontoen\n"
        "ssh -i ~/.ssh/copilotdiag_rpi copilotdiag@ipr-prod-zero2.local"
    )

    m.p("En fast post i ~/.ssh/config sparer skrivearbejde og bruges automatisk af scp "
        "og rsync:")
    m.code(
        "Host ipr-prod\n"
        "    HostName ipr-prod-zero2.local\n"
        "    User meibye\n"
        "    IdentityFile ~/.ssh/ipr_rpi\n"
        "    ServerAliveInterval 30"
    )
    m.p("Derefter er ssh ipr-prod og scp fil.txt ipr-prod:~/ tilstrækkeligt.")

    m.note("Trin 00 sætter ClientAliveInterval 60 og ClientAliveCountMax 3 i "
           "/etc/ssh/sshd_config, så inaktive sessioner lukkes efter omkring tre minutter. "
           "Det er tilsigtet. Sæt ServerAliveInterval i klientens config, hvis en session "
           "skal holdes åben under en lang kørsel.", "info")

    m.p("Når forbindelsen ikke kan etableres", bold=True)
    m.table(
        ["Symptom", "Sandsynlig årsag", "Handling"],
        [
            ["Could not resolve hostname",
             "mDNS virker ikke på PC'ens net, eller enheden er ikke på nettet.",
             "Brug IP-adressen i stedet. Find den på routeren eller gå via hotspottet "
             "på 10.42.0.1."],
            ["Connection refused",
             "SSH er ikke slået til på imaget.",
             "Opret filen ssh på boot-partitionen, og start enheden igen."],
            ["Permission denied (publickey)",
             "Nøglen ligger ikke i authorized_keys, eller rettighederne er for løse.",
             "Kontrollér chmod 700 ~/.ssh og chmod 600 ~/.ssh/authorized_keys på enheden."],
            ["REMOTE HOST IDENTIFICATION HAS CHANGED",
             "Enheden er provisioneret på ny og har fået en ny værtsnøgle.",
             "Fjern den gamle post med ssh-keygen -R ipr-prod-zero2.local"],
            ["Forbindelsen dør midt i en kørsel",
             "Wi-Fi-strømbesparelse eller SSH-timeout.",
             "Kør lange opgaver under tmux, så de overlever et afbrud."],
        ],
        widths=[4.2, 4.6, 6.8],
        caption="Almindelige SSH-fejl og deres afhjælpning.",
    )

    m.h2("3.3 Overfør projektfilerne til enheden")
    m.p("Trin 00 kloner selv repositoriet fra REPO_URL, hvis enheden har internetadgang. "
        "Produktionsenheden har det typisk ikke, og så skal filerne overføres fra "
        "administratorens PC. To filer skal altid overføres manuelt, fordi de ikke ligger "
        "i git.")

    m.note("Hver kommando herunder er mærket med, hvor den køres. Kommandoer mærket "
           "På PC'en køres fra repositoriets rod på administratorens PC — altså den mappe, "
           "der indeholder provision/ og scripts/. Stien ./ i rsync- og scp-kommandoerne "
           "henviser til netop denne mappe, og køres de fra et andet sted, overføres de "
           "forkerte filer.", "warn")
    m.table(
        ["Hvor kommandoen køres", "Sti til repositoriets rod"],
        [
            ["Windows PowerShell — standardvalget", "D:\\sandbox\\ipr-keyboard"],
            ["Git Bash", "/d/sandbox/ipr-keyboard"],
            ["WSL (Ubuntu)", "/mnt/d/sandbox/ipr-keyboard"],
            ["Enheden", "~/dev/ipr-keyboard — svarer til REPO_DIR i /opt/ipr_common.env"],
        ],
        widths=[5.6, 10.0],
        mono_cols=(1,),
        caption="Repositoriets rod skrives forskelligt afhængigt af, hvilken skal "
                "kommandoen køres i. Kommandoerne i dette afsnit forudsætter disse stier.",
    )
    m.code(
        "# På PC'en — skift til repositoriets rod først\n"
        "cd D:\\sandbox\\ipr-keyboard          # PowerShell\n"
        "cd /d/sandbox/ipr-keyboard          # Git Bash\n"
        "cd /mnt/d/sandbox/ipr-keyboard      # WSL\n"
        "\n"
        "ls provision/ scripts/              # kontrollér at du står det rigtige sted"
    )

    m.note("Kommandoer, der fortsætter på næste linje, bruger omvendt skråstreg i bash og "
           "WSL, men accent grave i PowerShell. Kopieres et bash-eksempel direkte ind i "
           "PowerShell, fejler det med Missing expression after unary operator '--', fordi "
           "de efterfølgende linjer opfattes som selvstændige kommandoer. Skriv kommandoen "
           "på én linje i PowerShell, eller udskift linjeskiftstegnet.", "warn")

    m.table(
        ["Hvad", "Hvorhen på enheden", "Hvorfor"],
        [
            ["Projektmappen", "$REPO_DIR — typisk /home/meibye/dev/ipr-keyboard",
             "Kildekode, skripts og provisioneringstrin."],
            ["provision/common.env — lokal kopi, som du selv opretter",
             "/opt/ipr_common.env",
             "Enhedsspecifikke værdier. Indeholder hemmeligheder og er udeladt af git."],
            ["Offentlig nøgle til fejlsøgning", "/tmp/copilot_pubkey.txt",
             "Læses af trin 05, så copilotdiag-kontoen får adgang uden manuel indtastning."],
        ],
        widths=[4.2, 5.8, 5.6],
        caption="Filer, der skal på plads på enheden før provisioneringen køres.",
    )

    m.p("Overfør kun det nødvendige", bold=True)
    m.p("Enheden har kun brug for en delmængde af repositoriet. Overfør netop den "
        "delmængde — ikke hele mappen.")
    m.table(
        ["Skal med", "Hvorfor"],
        payload_rows(),
        widths=[4.2, 11.4],
        mono_cols=(0,),
        caption="Filer og mapper, enheden har brug for. Alt andet i repositoriet kan "
                "udelades. Tabellen genereres ved bygning af manualen ud fra "
                "scripts/deploy/make_payload.sh, som er den gældende liste.",
    )

    m.note("Overfør aldrig hele mappen med scp -r eller rsync uden filtre. Så følger "
           "config.json, users.json, secret_key.txt og admin_initial_password.txt med — "
           "filer, der er enhedsspecifikke og udeladt af git. De overskriver enhedens egen "
           "konfiguration og brugerdatabase og lægger PC'ens sessionsnøgle og en "
           "administratoradgangskode i klartekst på enheden. Med følger desuden .venv/, "
           "som er bygget til PC'ens processorarkitektur og ikke kan bruges på enheden.",
           "danger")

    m.p("Hvilken skal skal jeg bruge?", bold=True)
    m.p("Overførselsskripterne er bash-skripter. De kan ikke køres direkte i PowerShell, "
        "som ikke har bash. Vælg én af disse tre måder — de gør det samme:")
    m.table(
        ["Skal", "Sådan startes skriptet", "Bemærkning"],
        [
            ["Git Bash", "./scripts/deploy/host_push_to_device.sh ipr-prod",
             "Enklest. Følger med Git til Windows. Åbn Git Bash og gå til "
             "/d/sandbox/ipr-keyboard."],
            ["PowerShell", "bash ./scripts/deploy/host_push_to_device.sh ipr-prod",
             "Virker, fordi bash kaldes eksplicit. Kør fra D:\\sandbox\\ipr-keyboard."],
            ["WSL (Ubuntu)", "./scripts/deploy/host_push_to_device.sh ipr-prod",
             "Nødvendig, hvis der skal bruges rsync. Gå til "
             "/mnt/d/sandbox/ipr-keyboard. Kræver wsl_setup_ssh.sh først."],
        ],
        widths=[2.8, 6.8, 6.0],
        caption="De tre måder at starte overførselsskriptet fra Windows. Alle tre kører "
                "det samme skript.",
    )

    m.note("Bruges WSL, kræves en engangsopsætning først. WSL deler ikke Windows-brugerens "
           "~/.ssh: en frisk distribution har hverken nøgler eller config, så ipr-prod "
           "opfattes som et bogstaveligt værtsnavn med WSL-brugerens navn, og alt fejler "
           "eller falder tilbage til adgangskode. Dertil kommer, at .local-navne ikke kan "
           "slås op under WSL2. Begge dele ordnes af scripts/deploy/wsl_setup_ssh.sh, som "
           "kopierer nøgler og config ind i WSL med korrekte rettigheder og indsætter "
           "IP-adresser, slået op via Windows.", "warn")
    m.code(
        "# Én gang pr. WSL-distribution\n"
        "./scripts/deploy/wsl_setup_ssh.sh\n"
        "\n"
        "# Kontrollér resultatet\n"
        "ssh ipr-prod true && echo ok"
    )
    m.p("Et symbolsk link fra WSL til Windows-mappen virker ikke: filer på Windows-drevet "
        "fremstår med rettigheden 0777, og ssh afviser en privat nøgle, der er så åben. "
        "Nøglerne skal kopieres ind i Linux-filsystemet. Kør skriptet igen, hvis enhedens "
        "IP-adresse ændrer sig.")

    m.p("Hele overførslen med ét skript — anbefalet", bold=True)
    m.p("scripts/deploy/host_push_to_device.sh udfører alle trin på PC-siden: pakker "
        "arkivet med make_payload.sh, overfører det sammen med miljøfilen og den "
        "offentlige nøgle, pakker ud på enheden, gendanner eksekverbar-flaget og lægger "
        "miljøfilen på plads i /opt.")
    m.code(
        "# I Git Bash, i repositoriets rod\n"
        "cd /d/sandbox/ipr-keyboard\n"
        "\n"
        "# Miljøfilen skal findes først — opret den fra skabelonen, hvis den mangler\n"
        "cp provision/common.env.example provision/common.env\n"
        "notepad provision/common.env      # sæt DEVICE_TYPE, HOSTNAME, BT_DEVICE_NAME\n"
        "\n"
        "# Se hvad der ville ske, uden at ændre noget\n"
        "./scripts/deploy/host_push_to_device.sh ipr-prod --dry-run\n"
        "\n"
        "# Udfør overførslen\n"
        "./scripts/deploy/host_push_to_device.sh ipr-prod"
    )
    m.table(
        ["Tilvalg", "Virkning"],
        [
            ["HOST", "Værtsalias fra ~/.ssh/config. Standard: ipr-prod. Brug aliasset — "
                     "ikke det fulde værtsnavn, se advarslen ovenfor."],
            ["--dry-run", "Vis alle handlinger uden at udføre dem."],
            ["--with-tests", "Tag også tests/ med. Kun relevant for udviklingsenheden."],
            ["--env FIL", "Anden miljøfil end provision/common.env."],
            ["--pubkey FIL", "Anden offentlig nøgle end ~/.ssh/copilotdiag_rpi.pub."],
            ["--remote-dir STI", "Anden placering end ~/dev/ipr-keyboard på enheden."],
            ["--skip-env, --skip-pubkey", "Undlad at overføre miljøfil eller nøgle."],
        ],
        widths=[4.6, 11.0],
        mono_cols=(0,),
        caption="Tilvalg til scripts/deploy/host_push_to_device.sh.",
    )
    m.note("Skriptet kontrollerer selv forbindelsen, inden det går i gang, og advarer, "
           "hvis nøglelogin ikke virker, eller hvis der er angivet et fuldt værtsnavn i "
           "stedet for et alias. Mangler miljøfilen, stopper det med en besked om, hvordan "
           "den oprettes — i stedet for at overføre en halv opsætning.", "tip")

    m.p("Kun pakning: make_payload.sh", bold=True)
    m.p("host_push_to_device.sh kalder scripts/deploy/make_payload.sh, som kan bruges "
        "alene, hvis arkivet skal overføres på anden vis — for eksempel på en USB-nøgle "
        "til en enhed helt uden netværk. Skriptet er den gældende liste over, hvad enheden "
        "har brug for; det kontrollerer arkivet bagefter og sletter det, hvis en "
        "enhedsspecifik fil alligevel er havnet i det.")
    m.code(
        "./scripts/deploy/make_payload.sh                 # -> /tmp/ipr-deploy.tgz\n"
        "./scripts/deploy/make_payload.sh --list          # vis fillisten\n"
        "./scripts/deploy/make_payload.sh -o D:/ipr.tgz   # anden placering\n"
        "./scripts/deploy/make_payload.sh --with-tests    # tag tests/ med"
    )
    m.p("Arkivet fylder omkring 380 KB mod cirka 29 MB for hele mappen.")

    m.p("Manuel overførsel", bold=True)
    m.p("Skal trinnene køres enkeltvis — for eksempel ved fejlsøgning — svarer "
        "host_push_to_device.sh til følgende:")
    m.code(
        "# På PC'en\n"
        "./scripts/deploy/make_payload.sh -o /tmp/ipr-deploy.tgz\n"
        "scp /tmp/ipr-deploy.tgz        ipr-prod:/tmp/\n"
        "scp provision/common.env       ipr-prod:/tmp/ipr_common.env\n"
        "scp ~/.ssh/copilotdiag_rpi.pub ipr-prod:/tmp/copilot_pubkey.txt\n"
        "\n"
        "# På enheden\n"
        "ssh ipr-prod\n"
        "mkdir -p ~/dev/ipr-keyboard\n"
        "tar xzf /tmp/ipr-deploy.tgz -C ~/dev/ipr-keyboard && rm /tmp/ipr-deploy.tgz\n"
        "find ~/dev/ipr-keyboard/scripts ~/dev/ipr-keyboard/provision \\\n"
        "  \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +\n"
        "sudo mv /tmp/ipr_common.env /opt/ipr_common.env\n"
        "sudo chmod 0600 /opt/ipr_common.env"
    )

    m.p("Overførsel med scp af hele mappen", bold=True)
    m.p("Metoden er kun relevant, hvis tar ikke er tilgængelig. Læs advarslen ovenfor "
        "først — hele mappen inklusive hemmeligheder og .venv/ overføres.")

    m.note("scp skriver ind i en mappe, der allerede findes — den opretter ikke "
           "målmappen, og -r ændrer ikke på det. På en nyinstalleret enhed findes hverken "
           "~/dev eller ~/dev/ipr-keyboard, og overførslen fejler med path canonicalization "
           "failed. Opret derfor målmappens overmappe først.", "warn")

    m.code(
        "# 1. På enheden — opret overmappen\n"
        "ssh ipr-prod \"mkdir -p ~/dev\"\n"
        "\n"
        "# 2. På PC'en — kør fra mappen OVER repositoriet, og navngiv mappen.\n"
        "#    Så opretter scp selv ipr-keyboard i målet.\n"
        "cd D:\\sandbox\n"
        "scp -r ipr-keyboard ipr-prod:/home/meibye/dev/\n"
        "\n"
        "# 3. Ryd op på enheden bagefter\n"
        "ssh ipr-prod \"cd ~/dev/ipr-keyboard && rm -rf .venv .git logs && rm -f secret_key.txt admin_initial_password.txt\""
    )

    m.note("Repositoriet indeholder kun skabelonen provision/common.env.example. Filen "
           "provision/common.env opretter du selv — den er med i .gitignore, så "
           "enhedsspecifikke værdier og hemmeligheder aldrig havner i git. Springes trin 3 "
           "over, fejler overførslen med stat local \"common.env\": No such file or "
           "directory.", "warn")

    m.p("Værdier, der skal tilrettes pr. enhed. De øvrige standardværdier i skabelonen "
        "passer allerede til den beskrevne opsætning:")
    m.table(
        ["Variabel", "Produktionsenhed", "Udviklingsenhed"],
        [
            ["DEVICE_TYPE", "target", "dev"],
            ["HOSTNAME", "ipr-prod-zero2", "ipr-dev-pi4"],
            ["BT_DEVICE_NAME", "IPR Keyboard", "IPR Keyboard (Dev)"],
        ],
        widths=[4.4, 5.6, 5.6],
        mono_cols=(0, 1, 2),
        caption="Enhedsspecifikke værdier i provision/common.env. Trin 00 kræver desuden "
                "REPO_URL, REPO_DIR, APP_USER, APP_GROUP og GIT_REF — de er korrekte som "
                "leveret i skabelonen.",
    )
    m.note("Brug værtsaliasset fra ~/.ssh/config — her ipr-prod — og ikke det fulde "
           "værtsnavn. Et alias som Host ipr-prod ipr-prod-zero2 matcher ikke "
           "ipr-prod-zero2.local, fordi mønstrene ikke indeholder .local. Skrives det fulde "
           "navn, bruges IdentityFile ikke, og ssh spørger om adgangskode i stedet for at "
           "bruge nøglen.", "tip")

    m.p("Overførsel med rsync — bedst ved gentagne udrulninger", bold=True)
    m.p("rsync overfører kun ændrede filer og bevarer rettigheder, herunder "
        "eksekverbar-flaget. Det gør den klart hurtigst, når den samme enhed opdateres "
        "mange gange.")
    m.note("Windows har ikke rsync — heller ikke i Git Bash, som kun leverer ssh og scp. "
           "rsync kræver WSL. Kør derfor kommandoen gennem WSL, hvor drev D: findes som "
           "/mnt/d.", "warn")
    m.code(
        "# På PC'en — engangsopsætning: giv WSL adgang til SSH-nøglen.\n"
        "# WSL har sin egen ~/.ssh, og en nøgle på /mnt/c har rettigheder,\n"
        "# som ssh afviser.\n"
        "wsl -d Ubuntu -- bash -c \"mkdir -p ~/.ssh && cp /mnt/c/Users/<windows-bruger>/.ssh/ipr_rpi ~/.ssh/ && chmod 600 ~/.ssh/ipr_rpi\"\n"
        "\n"
        "# Målmappen skal findes — rsync opretter kun det sidste led\n"
        "ssh ipr-prod \"mkdir -p ~/dev/ipr-keyboard\"\n"
        "\n"
        "# Selve overførslen — skrives på én linje, fordi den kaldes fra PowerShell.\n"
        "# Bemærk filtrene: de holder hemmeligheder og enhedsspecifikke filer tilbage.\n"
        "wsl -d Ubuntu -- rsync -avz --delete --chmod=D755,F644 --exclude '.git' --exclude '.venv' --exclude '__pycache__' --exclude 'docs' --exclude 'tests' --exclude 'logs' --exclude 'config.json' --exclude 'users.json' --exclude 'secret_key.txt' --exclude 'admin_initial_password.txt' /mnt/d/sandbox/ipr-keyboard/ ipr-prod:/home/meibye/dev/ipr-keyboard/\n"
        "\n"
        "# Gendan eksekverbar-flaget, som --chmod har fjernet\n"
        "wsl -d Ubuntu -- ssh ipr-prod \"find ~/dev/ipr-keyboard/scripts ~/dev/ipr-keyboard/provision \\\\( -name '*.sh' -o -name '*.py' \\\\) -exec chmod +x {} +\""
    )
    m.note("Brug værtsaliasset ipr-prod — ikke det fulde navn "
           "meibye@ipr-prod-zero2.local. WSL2 kan ikke slå .local-navne op, og "
           "kommandoen fejler med Could not resolve hostname. Aliasset peger på en "
           "IP-adresse, som wsl_setup_ssh.sh har indsat.", "warn")
    m.note("--chmod=D755,F644 er nødvendig. Filer på Windows-drevet fremstår med "
           "rettigheden 0777 set fra WSL, og uden tilvalget skriver rsync 0777 videre til "
           "enheden — også på modulerne under src/, som hverken skal være eksekverbare "
           "eller skrivbare for alle. Derfor følges overførslen af, at eksekverbar-flaget "
           "sættes igen på scripts/ og provision/.", "warn")

    m.p("Køres rsync i stedet inde fra en WSL-session, skrives kommandoen som sædvanligt "
        "med omvendt skråstreg som linjeskift:")
    m.code(
        "# I WSL, i repositoriets rod\n"
        "cd /mnt/d/sandbox/ipr-keyboard\n"
        "\n"
        "rsync -avz --delete --chmod=D755,F644 \\\n"
        "  --exclude '.git' --exclude '.venv' --exclude '__pycache__' \\\n"
        "  --exclude 'docs' --exclude 'tests' --exclude 'logs' \\\n"
        "  --exclude 'config.json' --exclude 'users.json' \\\n"
        "  --exclude 'secret_key.txt' --exclude 'admin_initial_password.txt' \\\n"
        "  ./ ipr-prod:/home/meibye/dev/ipr-keyboard/\n"
        "\n"
        "ssh ipr-prod \"find ~/dev/ipr-keyboard/scripts ~/dev/ipr-keyboard/provision \\\\\n"
        "  \\\\( -name '*.sh' -o -name '*.py' \\\\) -exec chmod +x {} +\""
    )
    m.p("Placér derefter miljøfilen korrekt. Kommandoerne køres på enheden — enten i en "
        "SSH-session eller via ssh ipr-prod \"…\":")
    m.code(
        "# På enheden\n"
        "sudo mv /tmp/ipr_common.env /opt/ipr_common.env\n"
        "sudo chmod 0600 /opt/ipr_common.env"
    )

    m.p("Overførsel af git-historik uden netværk", bold=True)
    m.p("Skal enheden beholde et fuldt git-repository — for eksempel for at kunne rulle "
        "tilbage med git checkout — så overfør et git-bundle i stedet for en kopi af "
        "filerne. Bundlet er én enkelt fil:")
    m.code(
        "# På PC'en, i repositoriets rod\n"
        "cd D:\\sandbox\\ipr-keyboard\n"
        "git bundle create ipr-keyboard.bundle --all\n"
        "scp ipr-keyboard.bundle meibye@ipr-prod-zero2.local:/tmp/\n"
        "\n"
        "# På enheden — første gang\n"
        "git clone /tmp/ipr-keyboard.bundle ~/dev/ipr-keyboard\n"
        "\n"
        "# På enheden — senere opdateringer fra et nyt bundle\n"
        "cd ~/dev/ipr-keyboard\n"
        "git pull /tmp/ipr-keyboard.bundle main"
    )

    m.note("Windows kender ikke Unix' eksekverbar-flag. Filer overført fra en Windows-PC "
           "med scp eller rsync uden -a lander uden +x, og skripterne fejler med Permission "
           "denied. Gendan flaget på enheden efter hver overførsel fra Windows.", "warn")
    m.code(
        "# På enheden\n"
        "find ~/dev/ipr-keyboard/scripts \\( -name '*.sh' -o -name '*.py' \\) \\\n"
        "  -exec chmod +x {} +\n"
        "find ~/dev/ipr-keyboard/provision -name '*.sh' -exec chmod +x {} +"
    )
    m.p("Kun filer under scripts/ og provision/ skal være eksekverbare. Modulerne under "
        "src/ipr_keyboard/ importeres og må ikke have flaget sat.")

    m.p("Kontrollér overførslen", bold=True)
    m.code(
        "# På PC'en — mappen er uden betydning her\n"
        "ssh meibye@ipr-prod-zero2.local \"ls -l ~/dev/ipr-keyboard/provision/*.sh\"\n"
        "ssh meibye@ipr-prod-zero2.local \"sudo -S test -r /opt/ipr_common.env && echo env ok\""
    )

    m.h2("3.4 Forbered miljøfilen")
    m.p("Provisioneringen kræver, at /opt/ipr_common.env findes. Er filen allerede "
        "overført fra PC'en som beskrevet i afsnit 3.3, er dette afsnit klaret — kontrollér "
        "blot med sudo -S test -r /opt/ipr_common.env. Ellers oprettes den på enheden ud fra "
        "skabelonen. Kommandoerne køres på enheden, i repositoriets rod — typisk "
        "~/dev/ipr-keyboard, fordi stien provision/common.env.example er relativ:")
    m.code(
        "# På enheden, i repositoriets rod\n"
        "cd ~/dev/ipr-keyboard\n"
        "sudo cp provision/common.env.example /opt/ipr_common.env\n"
        "sudo chmod 0600 /opt/ipr_common.env\n"
        "sudo nano /opt/ipr_common.env      # tilret bruger, værtsnavn, repo-sti"
    )

    m.h2("3.5 Kør guiden")
    m.p("Den anbefalede vej er scripts/deploy/device_bootstrap.sh. Den kontrollerer, at "
        "overførslen fra afsnit 3.3 er komplet, viser hvilken identitet enheden er ved at "
        "få, og starter derefter guiden. Kontrollen alene kan køres med --check-only.")
    m.code(
        "# På enheden\n"
        "sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh --check-only\n"
        "sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh"
    )
    m.note("Skriptet advarer, hvis HOSTNAME i miljøfilen afviger fra enhedens nuværende "
           "navn. Navnet skifter under trin 02, og den igangværende SSH-forbindelse mister "
           "sit navneopslag — genopret forbindelsen som <nyt navn>.local bagefter.", "warn")
    m.p("Guiden kan også startes direkte. Den kører trin 00 til 06 med "
        "genoptagelsespunkter:")
    m.code("sudo ./provision/provision_wizard.sh")

    m.p("Trin 00 og DEVICE_TYPE", bold=True)
    m.p("Trin 00 henter kildekoden på to forskellige måder afhængigt af DEVICE_TYPE i "
        "/opt/ipr_common.env. Det er afgørende for en produktionsenhed uden "
        "internetadgang.")
    m.table(
        ["DEVICE_TYPE", "Hvad trin 00 gør", "Forudsætning"],
        [
            ["dev", "Kloner REPO_URL og checker GIT_REF ud. Opretter desuden en "
                    "SSH-nøgle og viser vejledning til GitHub.",
             "Enheden har internetadgang."],
            ["target", "Kloner ikke. Kontrollerer i stedet, at de overførte filer er "
                       "på plads, og springer git fetch, git checkout og "
                       "GitHub-vejledningen over.",
             "Filerne er overført som beskrevet i afsnit 3.3."],
        ],
        widths=[2.6, 8.4, 4.6],
        mono_cols=(0,),
        caption="Trin 00's opførsel afhænger af DEVICE_TYPE. Findes der allerede et "
                "git-checkout i REPO_DIR, bruges det uanset indstillingen.",
    )
    m.note("Sættes DEVICE_TYPE forkert til dev på en enhed, der er seedet med "
           "make_payload.sh, fejler trin 00 med destination path already exists and is "
           "not an empty directory. git clone nægter at klone ned i en mappe, der ikke er "
           "tom — og en produktionsenhed uden netværk kan alligevel ikke klone.", "warn")
    m.p("Mangler filerne, stopper trin 00 med en liste over, hvad der ikke blev fundet, "
        "og henviser til overførselsskriptet. Versionen på en target-enhed er den, "
        "administratoren pakkede — enheden har ingen git-historik, og verifikations"
        "rapporten fra trin 06 skriver derfor \"transferred payload\" i stedet for "
        "commit og branch.")
    m.p("Skal trinene køres manuelt — for eksempel ved fejlsøgning af et enkelt trin:")
    m.code(
        "sudo ./provision/00_bootstrap.sh        # validerer miljø, henter repo\n"
        "sudo ./provision/01_os_base.sh          # OS-pakker og Bluetooth-baseline\n"
        "sudo reboot\n"
        "sudo ./provision/02_device_identity.sh  # værtsnavn og Bluetooth-navn\n"
        "sudo reboot\n"
        "sudo ./provision/03_app_install.sh      # Python-miljø og pakke\n"
        "sudo ./provision/04_enable_services.sh  # installerer og aktiverer tjenester\n"
        "sudo ./provision/05_copilot_debug_tools.sh   # valgfrit\n"
        "sudo ./provision/06_verify.sh           # verifikationsrapport"
    )

    m.p("Trin 04 udfører internt følgende i rækkefølge:")
    m.bullets([
        "scripts/service/svc_install_bt_gatt_hid.sh — BLE-dæmon og agent-enheder",
        "scripts/ble/ble_install_helper.sh — afhængigheder og bt_kb_send",
        "scripts/service/svc_install_systemd.sh — ipr_keyboard.service",
        "scripts/ble/ble_setup_extras.sh — supplerende Bluetooth-opsætning",
        "scripts/service/svc_enable_services.sh — aktivering",
        "installation af ipr-provision.service samt TLS-certifikater",
    ], numbered=True)

    m.h2("3.6 Efter provisioneringen")
    m.p("Hent hotspot-oplysningerne og notér dem — de skal bruges ved nødadgang:")
    m.code("sudo ./provision/07_show_info.sh\nsudo cat /etc/ipr-hotspot.secret")

    m.p("Kontrollér at alt kører:")
    m.code(
        "systemctl status ipr_keyboard.service bt_hid_ble.service \\\n"
        "               bt_hid_agent_unified.service ipr-provision.service\n"
        "./scripts/diag_status.sh\n"
        "curl -k https://localhost/health"
    )

    m.h2("3.7 Montér IRIS-skanneren")
    m.p("Applikationen læser almindelige filer fra en mappe. Skanneren skal derfor være "
        "monteret på et fast sted, som matcher IrisPenFolders i config.json.")
    m.p("Masselagerenheder — permanent montering via UUID i /etc/fstab:", bold=True)
    m.code("sudo ./scripts/usb_setup_mount.sh /dev/sda1 /mnt/irispen")
    m.p("MTP-enheder, som ikke eksponerer et blokdrev:", bold=True)
    m.code("sudo apt install jmtpfs\nsudo ./scripts/usb_mount_mtp.sh    # skifter mellem montér og afmontér")
    m.note("usb_setup_mount.sh tager en sikkerhedskopi af /etc/fstab, før den ændrer den, "
           "og bruger nofail — en manglende skanner blokerer derfor ikke opstarten.", "tip")

    m.h2("3.8 Første login på dashboardet")
    m.rich([
        ("Første gang webserveren starter, oprettes en administratorkonto ved navn ", ""),
        ("admin", "c"),
        (". Den tilfældige startadgangskode skrives til filen ", ""),
        ("admin_initial_password.txt", "c"),
        (" i projektroden.", ""),
    ])
    m.bullets([
        "Log ind på dashboardet med admin og adgangskoden fra filen.",
        "Skift adgangskoden med det samme under Indstillinger → Konto.",
        "Slet derefter admin_initial_password.txt fra enheden.",
        "Opret personlige konti til de administratorer, der skal have adgang.",
    ], numbered=True)
    m.note("admin_initial_password.txt indeholder en adgangskode i klartekst. Filen er "
           "udelukket fra git via .gitignore, men den bliver liggende på enheden, indtil "
           "den slettes manuelt. Slet den som en fast del af idriftsættelsen.", "danger")

    m.h2("3.9 Par den første vært")
    m.bullets([
        "Kontrollér at bt_hid_agent_unified.service og bt_hid_ble.service kører.",
        "Sæt værten i tilføj-enhed-tilstand.",
        "Par med enhedens BLE-tastaturidentitet (navnet sat i trin 02).",
        "Verificér at værten abonnerer på notifikationer, og send en testtekst:",
    ], numbered=True)
    m.code('bt_kb_send "smoke test"')
    m.p("Skal Bluetooth-adressen bruges i Windows-format (uden koloner, versaler):")
    m.code("./scripts/ble/ble_show_bt_mac_for_windows.sh")

    # ---------------------------------------------------------------- 4
    m.h1("4. Konfiguration", new_page=True)

    m.h2("4.1 Applikationskonfiguration — config.json")
    m.p("Filen ligger i projektroden og indlæses af ConfigManager. Ved førstegangskørsel "
        "kopieres config.default.json, hvis config.json mangler. Ændringer via dashboardet "
        "skrives tilbage til filen.")
    m.table(
        ["Felt", "Standard", "Betydning"],
        [
            ["IrisPenFolders", '["/mnt/irispen/…/Scan text and save"]',
             "Liste af mapper, der overvåges. Alle overvåges parallelt, hver med sin egen "
             "tidsstempelmarkering."],
            ["DeleteFiles", "true", "Slet filen, når teksten er sendt."],
            ["Logging", "true", "Slå applikationslogning til eller fra."],
            ["MaxFileSize", "1048576", "Største fil i bytes, der læses. Større filer springes over."],
            ["LogPort", "443", "Port for webserveren. Ændring træder først i kraft efter genstart."],
            ["LogLevel", "INFO", "DEBUG, INFO, WARNING, ERROR eller OFF."],
            ["PairingTimeoutSeconds", "120", "Hvor længe enheden bliver i parringstilstand."],
            ["ReadTimeoutSeconds", "10", "Maksimal ventetid ved læsning af en fil."],
            ["PollIntervalSeconds", "1.0", "Interval mellem mappescanninger. Højere værdi "
                                           "sparer CPU på Pi Zero 2 W."],
            ["StatusIntervalSeconds", "5", "Interval mellem statusopdateringer til browseren (SSE)."],
            ["NetworkMode", '"dhcp"', 'Enten "dhcp" eller "static".'],
            ["StaticIP / StaticNetmask / StaticGateway", '"" / 255.255.255.0 / ""',
             "Bruges kun når NetworkMode er static."],
            ["TlsCertFile / TlsKeyFile", "/etc/ipr-ssl/server.crt og .key",
             "Læses ved opstart. Eksponeres ikke via konfigurations-API'et."],
            ["GpioEnabled", "true", "Slå reed-kontakt og LED fra på maskiner uden GPIO."],
            ["GpioReedPin", "27", "BCM-nummer for reed-kontakten."],
            ["GpioLedRPin / GpioLedGPin / GpioLedBPin", "22 / 23 / 24",
             "BCM-numre for LED'ens tre farvekanaler."],
            ["GpioLedIdleSeconds", "30", "Hvor længe LED'en viser status efter en berøring."],
        ],
        widths=[4.4, 3.4, 7.8],
        mono_cols=(0, 1),
        caption="Felter i config.json med standardværdier og virkning.",
    )

    m.note("Standardværdien for LogPort er 443 i den kode og den konfiguration, der "
           "leveres til enheder, mens config.default.json angiver 8080. Kontrollér altid den "
           "faktiske værdi i config.json på enheden, før du fejlsøger portbinding.", "warn")

    m.h2("4.2 Konfiguration via dashboardet")
    m.p("Skærmen Indstillinger dækker de felter, der normalt skal ændres i drift:")
    m.bullets([
        ("Netværk — ", "webport, DHCP eller statisk adressering med IP, netmaske og gateway."),
        ("Bluetooth — ", "automatisk genforbindelse og parringstimeout."),
        ("Pen/skanner — ", "automatisk detektion, læsetimeout, pollinterval og listen over "
                           "overvågede mapper."),
        ("Diagnostik — ", "logniveau og statusopdateringsinterval."),
        ("Strøm — ", "genstart og nedlukning, begge med bekræftelse."),
    ])
    m.note("Ændring af netværkstilstand kræver administratorrolle og confirm=true i "
           "API-kaldet. Forbindelsen afbrydes kortvarigt, hvis IP-adressen ændres — "
           "sørg for at have hotspot-adgang som reserveudvej.", "warn")

    m.h2("4.3 Systemkonfiguration")
    m.table(
        ["Fil", "Formål", "Vigtige indstillinger"],
        [
            ["/opt/ipr_common.env", "Miljø for provisionering og skripts.",
             "Applikationsbruger, projektsti, værtsnavn."],
            ["/etc/default/ipr-provision", "Adfærd for hotspottet.",
             "HOTSPOT_MODE=on-demand (standard) eller always\nHOTSPOT_GPIO_PIN=27 (valgfri "
             "hardwaregate)"],
            ["/etc/default/bt_hid_agent_unified", "Parringsagentens adfærd.",
             "Agentkapabilitet, standard NoInputNoOutput. Styres af "
             "scripts/lib/bt_agent_unified_env.sh."],
            ["config.json", "Applikationskonfiguration.", "Se afsnit 4.1."],
            ["users.json", "Konti til dashboardet.", "Redigér via UI, ikke i hånden."],
        ],
        widths=[4.6, 4.4, 6.6],
        mono_cols=(0,),
        caption="Konfigurationsfiler uden for applikationen.",
    )

    m.h2("4.4 Miljøvariable for afsendelsesvejen")
    m.p("Disse variable beskytter mod, at en uafleverbar afsendelse blokerer alle "
        "efterfølgende. Ændr dem kun med god grund.")
    m.table(
        ["Variabel", "Standard", "Virkning"],
        [
            ["BLE_QUEUE_DRAIN_WAIT_SECS", "5",
             "Hvor længe dæmonens arbejdstråd venter på at tømme køen, før den igen åbner "
             "FIFO'en for læsning."],
            ["BLE_QUEUE_MAX_CHARS", "4096", "Maksimal størrelse på dæmonens interne kø."],
            ["BT_KB_WRITE_TIMEOUT_SECS", "5 (tekst) / 30 (fil)",
             "Tidsgrænse for bt_kb_send og bt_kb_send_file."],
        ],
        widths=[5.4, 3.0, 7.2],
        mono_cols=(0, 1),
        caption="Tidsgrænser i afsendelsesvejen.",
    )

    m.h2("4.5 GPIO — reed-kontakt og RGB-LED")
    m.table(
        ["Signal", "BCM", "Fysisk ben", "Note"],
        [
            ["Reed-kontakt", "27", "13", "Normalt åben, software-pull-up"],
            ["LED rød", "22", "15", "150 Ω i serie"],
            ["LED grøn", "23", "16", "150 Ω i serie"],
            ["LED blå", "24", "18", "22 Ω i serie (højere Vf)"],
            ["Fabriksnulstilling (ældre)", "17", "11", "Må ikke genbruges"],
        ],
        widths=[5.0, 2.0, 2.6, 6.0],
        caption="Benallokering. Fælles katode til GND. Rød og grøn trækker 8–9 mA, "
                "blå cirka 13,6 mA — alle under grænsen på 16 mA pr. ben. Modstanden på "
                "blå må ikke sættes lavere end 22 Ω.",
    )
    m.p("Detaljeret ledningsdiagram, modstandsberegninger og montering i Flirc-kabinettet "
        "findes i docs/hardware/gpio-wiring.md. Sæt GpioEnabled til false på maskiner uden "
        "RPi.GPIO — modulet deaktiverer i øvrigt sig selv, hvis importen fejler.")

    # ---------------------------------------------------------------- 5
    m.h1("5. Adgang, netværk og hotspot", new_page=True)

    m.figure("fig09_adgangsveje.png",
             "De to adgangsveje. Hjemmenettet bruges i normal drift; hotspottet er "
             "nødadgang, der virker uden netværk.")

    m.h2("5.1 Normal adgang")
    m.p("Dashboardet nås på https://<værtsnavn>.local/ på den port, der er sat i LogPort. "
        "Adgang kræver login. Administratorer får desuden et Setup-punkt i navigationen, "
        "der fører direkte til setup-siderne uden endnu et login.")

    m.h2("5.2 Opsætningshotspottet")
    m.p("Hotspottet er slukket som standard (on-demand) for at holde enheden usynlig. Det "
        "startes af én af følgende udløsere, som skriptet evaluerer i denne rækkefølge:")
    m.table(
        ["Udløser", "Sådan aktiveres den", "Hvornår bruges den"],
        [
            ["Markørfil", "Opret en tom fil ved navn IPR_SETUP på /boot/firmware "
                          "(FAT32, kan skrives fra enhver PC).",
             "Sidste udvej — kræver SD-kortlæser."],
            ["Tredobbelt tænd/sluk", "Tænd og sluk enheden tre gange inden for 120 sekunder.",
             "Når magneten ikke er tilgængelig."],
            ["GPIO-gate", "Sæt HOTSPOT_GPIO_PIN i /etc/default/ipr-provision.",
             "Ældre hardwareopsætninger."],
            ["HOTSPOT_MODE=always", "Sæt i /etc/default/ipr-provision.",
             "Udviklings- og testenheder."],
            ["Reed-kontakt", "Hold magneten på plads i mindst 3 sekunder og slip.",
             "Normal drift. Håndteres af gpio_monitor, ikke af hotspot-skriptet."],
        ],
        widths=[3.4, 6.6, 5.6],
        caption="Udløsere for hotspottet. De fire første evalueres af "
                "net_provision_hotspot.sh ved opstart i den viste rækkefølge.",
    )
    m.p("Manuel styring:")
    m.code(
        "sudo systemctl start ipr-provision.service    # tænd hotspot\n"
        "sudo systemctl stop  ipr-provision.service    # sluk hotspot\n"
        "sudo cat /etc/ipr-hotspot.secret              # SSID og adgangskode"
    )
    m.p("Tilslut derefter til SSID'et ipr-setup-xxxx og åbn https://10.42.0.1/setup/. "
        "Log ind som brugeren ipr med adgangskoden fra PASS-linjen i "
        "/etc/ipr-hotspot.secret.")

    m.note("SERVICES.md og docs/architecture/ARCHITECTURE.md beskriver hotspottet som "
           "permanent og altid tændt. Skriptet net_provision_hotspot.sh er siden ændret til "
           "on-demand som standard. Skriptets adfærd er den gældende — kontrollér "
           "HOTSPOT_MODE i /etc/default/ipr-provision på den konkrete enhed.", "warn")

    m.h2("5.3 Setup-UI'ets sider")
    m.table(
        ["Side", "Funktion"],
        [
            ["Home", "Enhedsnavn, hotspot-oplysninger, IP-adresser."],
            ["Status", "Tjenestestatus og Bluetooth-forbindelser."],
            ["WiFi", "Scan efter netværk og gem legitimationsoplysninger."],
            ["Logs", "Seneste logoutput fra enhedens tjenester."],
            ["System", "Forny SSL-certifikat, genstart eller sluk."],
        ],
        widths=[3.2, 12.4],
        caption="Setup-UI'ets sider på /setup/.",
    )

    m.h2("5.4 Netværksnulstilling")
    m.p("Magneten holdt i 10 sekunder sletter alle Wi-Fi-profiler undtagen ipr-hotspot og "
        "genstarter enheden. Applikationsindstillinger, brugerkonti og logfiler berøres ikke. "
        "Samme resultat opnås manuelt:")
    m.code("sudo ./scripts/headless/net_factory_reset.sh")

    # ---------------------------------------------------------------- 6
    m.h1("6. Brugerkonti og roller", new_page=True)

    m.h2("6.1 Kontomodellen")
    m.p("Dashboardets konti gemmes i users.json i projektroden. Adgangskoder hashes med "
        "werkzeugs pbkdf2:sha256 — der gemmes aldrig klartekst. Rollemodellen har to niveauer.")
    m.table(
        ["Rolle", "Kan", "Kan ikke"],
        [
            ["Almindelig bruger",
             "Se status, hændelser, aktivitet og logs. Skifte egen adgangskode.",
             "Ændre netværk, administrere brugere eller åbne setup-siderne."],
            ["Administrator (is_admin)",
             "Alt ovenstående plus netværkskonfiguration, brugeradministration og direkte "
             "adgang til /setup/.",
             "Fjerne sin egen administratorrolle eller slette den sidste administratorkonto."],
        ],
        widths=[3.8, 6.2, 5.6],
        caption="Rollernes rettigheder.",
    )

    m.h2("6.2 Regler, der håndhæves i koden")
    m.bullets([
        "Brugernavn: 3–32 tegn, kun små bogstaver, cifre og understreg.",
        "Adgangskode: mindst 8 tegn.",
        "Der skal altid findes mindst én administrator — den sidste kan hverken "
        "nedgraderes eller slettes.",
        "Kontoen admin kan ikke slettes.",
        "Sessionen varer syv dage; cookien er markeret Secure.",
        "Setup-UI'ets login er begrænset til fem forsøg pr. IP-adresse pr. minut.",
    ])

    m.h2("6.3 To adskilte loginsystemer")
    m.p("Dashboardet og setup-UI'et bruger hver sit legitimationssæt. Dashboardet bruger "
        "konti fra users.json. Setup-UI'et bruger den faste bruger ipr med adgangskoden fra "
        "/etc/ipr-hotspot.secret. En administrator, der allerede er logget ind på "
        "dashboardet, får dog adgang til setup-siderne uden yderligere login.")

    # ---------------------------------------------------------------- 7
    m.h1("7. Sikkerhed", new_page=True)

    m.figure("fig11_sikkerhed.png",
             "Sikkerhedslagene fra netværkskant til data på disken.")

    m.h2("7.1 Indbyggede sikkerhedsfunktioner")
    m.table(
        ["Område", "Funktion"],
        [
            ["Angrebsflade",
             "Hotspottet er slukket som standard og kræver fysisk tilstedeværelse "
             "(magnet, strømcykling eller SD-kort) for at blive tændt."],
            ["Trådløs sikring",
             "Hotspottet bruger WPA2 med tilfældigt genereret SSID og adgangskode. "
             "Legitimationsoplysningerne ligger i /etc/ipr-hotspot.secret med tilstand 0600."],
            ["Transportsikkerhed",
             "HTTPS med et CA-signeret certifikat fra enhedens egen private CA i "
             "/etc/ipr-ssl/. Servernøglen er root:ipr-ssl med tilstand 0640. SAN dækker både "
             "10.42.0.1 og <værtsnavn>.local."],
            ["Certifikatlivscyklus",
             "ipr-cert-renew.timer forny serverets certifikat årligt og bevarer CA-nøglen, "
             "så klienter ikke skal geninstallere CA-certifikatet."],
            ["Autentificering",
             "Alle stier undtagen /health, /login, /logout, /api/auth/login og /setup kræver "
             "en session. API-kald uden session besvares med 401."],
            ["Kodeordsopbevaring",
             "pbkdf2:sha256 via werkzeug. Sessionsnøglen ligger i secret_key.txt med "
             "tilstand 0600 og kan overstyres med miljøvariablen SECRET_KEY."],
            ["Autorisation",
             "Rollen is_admin beskytter netværksændringer, brugeradministration og "
             "setup-siderne."],
            ["Bekræftelse af farlige handlinger",
             "Genstart, nedlukning og ændring af netværkskonfiguration kræver confirm=true "
             "i anmodningen og afvises ellers med 400."],
            ["Adskillelse af netværkskontekst",
             "Klienter på 10.42.0.0/24 sendes til setup-login frem for dashboard-login."],
            ["Hemmeligheder uden for versionsstyring",
             "config.json, users.json, secret_key.txt, admin_initial_password.txt og "
             "provision/common.env er udelukket i .gitignore."],
        ],
        widths=[4.4, 11.2],
        caption="Sikkerhedsfunktioner i den leverede løsning.",
    )

    m.h2("7.2 Obligatoriske tiltag ved idriftsættelse")
    m.bullets([
        "Skift admin-kontoens adgangskode, og slet admin_initial_password.txt.",
        "Opret personlige konti; undgå at dele admin-kontoen.",
        "Distribuér CA-certifikatet fra https://10.42.0.1/setup/ca.crt til de PC'er, der "
        "skal bruge dashboardet, så browseradvarsler forsvinder — og brugerne ikke vænner "
        "sig til at klikke advarsler væk.",
        "Bekræft at HOTSPOT_MODE ikke står til always på produktionsenheder.",
        "Notér hotspot-legitimationsoplysningerne et sikkert sted — de er nødadgangen.",
        "Kontrollér filrettigheder efter manuelle indgreb: /etc/ipr-hotspot.secret (0600), "
        "secret_key.txt (0600), /etc/ipr-ssl/server.key (0640 root:ipr-ssl).",
        "Fjern eventuelle efterladte legacy-enheder fra tidligere installationer.",
    ], numbered=True)

    m.h2("7.3 Risici, du bør kende")
    m.table(
        ["Forhold", "Konsekvens", "Håndtering"],
        [
            ["Enheden er et HID-tastatur for værten.",
             "Alt, der sendes, tastes ind i det aktive vindue på den parrede PC.",
             "Par kun med kendte værter. Instruér brugerne i at låse PC'en, når de går fra "
             "arbejdspladsen."],
            ["Selvsigneret CA.",
             "Browsere advarer, indtil CA-certifikatet er installeret.",
             "Rul CA-certifikatet ud centralt frem for at lære brugerne at ignorere advarsler."],
            ["Fysisk adgang giver hotspot-adgang.",
             "Den, der kan røre enheden, kan tænde opsætningsnetværket.",
             "Placér enheden i et aflåst eller overvåget område."],
            ["BLE-parringsagenten bruger NoInputNoOutput.",
             "Parring sker uden PIN-bekræftelse.",
             "Par i et kontrolleret miljø, og kontrollér den parrede vært bagefter med "
             "bluetoothctl devices Connected."],
            ["Dashboardet kører Flasks indbyggede server.",
             "Ikke beregnet til eksponering mod internettet.",
             "Hold enheden på et betroet lokalnet. Eksponér den aldrig direkte mod internettet."],
        ],
        widths=[4.6, 5.2, 5.8],
        caption="Kendte risici og anbefalet håndtering.",
    )

    # ---------------------------------------------------------------- 8
    m.h1("8. Opdatering af softwaren", new_page=True)

    m.figure("fig10_opdatering.png",
             "Opdateringsforløbet med sikkerhedskopi, udrulning og verifikation.")

    m.h2("8.1 Standardforløb")
    m.code(
        "# 1. Sikkerhedskopi af enhedsspecifikke filer\n"
        "sudo cp config.json users.json /root/backup-$(date +%F)/\n"
        "sudo cp /etc/ipr-hotspot.secret /root/backup-$(date +%F)/\n"
        "\n"
        "# 2. Hent ny kode\n"
        "cd \"$IPR_PROJECT_ROOT/ipr-keyboard\" && git pull\n"
        "\n"
        "# 3. Rul ud\n"
        "sudo ./scripts/deploy/deploy_full_update.sh              # kode og skripts\n"
        "sudo ./scripts/deploy/deploy_full_update.sh --install-python   # også afhængigheder\n"
        "\n"
        "# 4. Verificér\n"
        "./scripts/diag_status.sh\n"
        'bt_kb_send "efter opdatering"'
    )

    m.p("deploy_full_update.sh udfører: valgfri geninstallation af Python-pakken i "
        "editerbar tilstand, installation af BLE-dæmoner og enhedsfiler, installation af "
        "Bluetooth-hjælpere, systemctl daemon-reload, generering af TLS-certifikater hvis de "
        "mangler, og genstart af alle tjenester i afhængighedsrækkefølge.")

    m.h2("8.2 Målrettede opdateringer")
    m.p("Ved du præcis, hvad der er ændret, undgår du unødige genstarter:")
    m.table(
        ["Skript", "Anvendelse"],
        [
            ["deploy_reinstall_package.sh", "Kun Python-pakken er ændret."],
            ["deploy_install_ble_daemons.sh", "BLE-dæmon eller enhedsfiler er ændret."],
            ["deploy_install_bt_helpers.sh", "bt_kb_send eller hjælpeskripts er ændret."],
            ["deploy_restart_app.sh", "Kun applikationen skal genstartes."],
            ["deploy_restart_all_services.sh", "Alle tjenester skal genstartes i rækkefølge."],
        ],
        widths=[6.2, 9.4],
        mono_cols=(0,),
        caption="Målrettede udrulningsskripts i scripts/deploy/.",
    )

    m.h2("8.3 Hvornår kræves --install-python?")
    m.bullets([
        ("Ja — ", "pyproject.toml, entry points eller afhængigheder er ændret."),
        ("Nej — ", "kun Python-kode, skripts eller skabeloner er ændret; pakken er "
                   "installeret i editerbar tilstand, så koden hentes direkte fra "
                   "projektmappen."),
    ])

    m.h2("8.4 Tilbagerulning")
    m.code(
        "cd \"$IPR_PROJECT_ROOT/ipr-keyboard\"\n"
        "git checkout <tidligere tag eller commit>\n"
        "sudo ./scripts/deploy/deploy_full_update.sh --install-python\n"
        "# gendan config.json og users.json fra sikkerhedskopien, hvis formatet er ændret\n"
        "systemctl status ipr_keyboard bt_hid_ble bt_hid_agent_unified"
    )
    m.note("Efter opdatering bør browsercachen tømmes med en hård genindlæsning "
           "(Ctrl+Shift+R). Dashboardet er en enkeltsides-applikation, og gamle sider kan "
           "ellers blive hængende.", "tip")

    m.h2("8.5 Udrulning til en enhed uden internetadgang")
    m.p("Produktionsenheden har normalt ikke internetadgang, og git pull i trin 2 kan derfor "
        "ikke gennemføres. Ny kode skal i stedet overføres fra administratorens PC med de "
        "metoder, der er beskrevet i afsnit 3.3. Resten af forløbet er uændret.")
    m.code(
        "# 1. På PC'en, i repositoriets rod — hent den ønskede version\n"
        "cd D:\\sandbox\\ipr-keyboard\n"
        "git pull && git checkout <tag eller commit>\n"
        "\n"
        "# 2. Sikkerhedskopiér enhedsspecifikke filer på enheden først\n"
        "ssh ipr-prod \"sudo mkdir -p /root/backup-$(date +%F) && \\\n"
        "  sudo cp config.json users.json /etc/ipr-hotspot.secret /root/backup-$(date +%F)/\"\n"
        "\n"
        "# 3. Overfør koden — kør i WSL fra /mnt/d/sandbox/ipr-keyboard,\n"
        "#    eller brug scp -r fra PowerShell (se afsnit 3.3)\n"
        "rsync -avz --delete --chmod=D755,F644 \\\n"
        "  --exclude '.git' --exclude '.venv' --exclude '__pycache__' \\\n"
        "  --exclude 'config.json' --exclude 'users.json' \\\n"
        "  ./ ipr-prod:/home/meibye/dev/ipr-keyboard/\n"
        "\n"
        "# 4. Rul ud på enheden\n"
        "ssh ipr-prod \"cd ~/dev/ipr-keyboard && sudo ./scripts/deploy/deploy_full_update.sh\"\n"
        "\n"
        "# 5. Verificér\n"
        "ssh ipr-prod \"cd ~/dev/ipr-keyboard && ./scripts/diag_status.sh\""
    )
    m.note("config.json og users.json er enhedsspecifikke og må ikke overskrives af "
           "udrulningen. Undtag dem eksplicit fra rsync som vist, eller undlad --delete.",
           "warn")
    m.p("Kræver den nye version ændrede Python-afhængigheder, kan --install-python ikke "
        "hente dem uden netværk. Enten gives enheden midlertidigt internetadgang, eller "
        "hjulpakkerne hentes på PC'en og overføres:")
    m.code(
        "# På PC'en, i repositoriets rod — samme platform og Python-version som enheden\n"
        "cd D:\\sandbox\\ipr-keyboard\n"
        "pip download . -d wheels/ \\\n"
        "  --platform linux_aarch64 --only-binary=:all:\n"
        "wsl -d Ubuntu -- rsync -avz /mnt/d/sandbox/ipr-keyboard/wheels/ ipr-prod:/tmp/wheels/\n"
        "\n"
        "# På enheden, i repositoriets rod\n"
        "cd ~/dev/ipr-keyboard\n"
        "source .venv/bin/activate && pip install --no-index --find-links /tmp/wheels -e ."
    )

    m.h2("8.6 Certifikatfornyelse")
    m.code(
        "systemctl list-timers ipr-cert-renew.timer         # kontrollér tidsplan\n"
        "sudo /usr/local/sbin/ipr-cert-renew.sh             # forny manuelt\n"
        "sudo ./scripts/headless/gen_ipr_ssl_cert.sh --renew   # kun serverbevis, CA bevares\n"
        "sudo ./scripts/headless/gen_ipr_ssl_cert.sh --force   # ny CA — klienter skal "
        "geninstallere"
    )
    m.note("Brug --force kun, hvis CA-nøglen er kompromitteret. Alle klienter, der har "
           "installeret det gamle CA-certifikat, skal derefter have det nye.", "warn")

    # ---------------------------------------------------------------- 9
    m.h1("9. Drift og overvågning", new_page=True)

    m.h2("9.1 Daglige kommandoer")
    m.code(
        "./scripts/diag_status.sh                 # samlet statusbillede (kør ikke som root)\n"
        "./scripts/service/svc_status_services.sh # tjenestestatus\n"
        "./scripts/service/svc_tail_all_logs.sh   # følg alle logs\n"
        "curl -k https://localhost/health         # sundhedstjek\n"
        "journalctl -u ipr_keyboard.service -n 200 --no-pager"
    )

    m.h2("9.2 Overvågningspunkter")
    m.table(
        ["Signal", "Sundt", "Handling ved afvigelse"],
        [
            ["systemctl is-active på de fire enheder", "active",
             "journalctl -u <enhed> og genstart enheden."],
            ["/health", "HTTP 200", "Kontrollér portbinding og TLS-certifikater."],
            ["Læser på FIFO'en", "sudo fuser -v /run/ipr_bt_keyboard_fifo giver output",
             "Ingen læser: genstart bt_hid_ble.service."],
            ["Monteringspunkt for skanneren", "mountpoint /mnt/irispen er sandt",
             "Montér igen; kontrollér USB-kabel og fstab-linje."],
            ["Bluetooth-forbindelse", "bluetoothctl devices Connected viser værten",
             "Kør parringsdiagnostikken."],
            ["Certifikatets udløb", "Mere end 30 dage tilbage",
             "Kør fornyelsen manuelt."],
            ["Diskplads og logstørrelse", "journald inden for sine grænser",
             "Sæt logniveauet ned fra DEBUG; tilpas journald-opbevaring."],
        ],
        widths=[4.8, 5.4, 5.4],
        caption="Hvad der bør holdes øje med i drift.",
    )

    m.note("Logniveauet DEBUG belaster både CPU og SD-kort på en Pi Zero 2 W. Brug det til "
           "fejlsøgning, og sæt niveauet tilbage til INFO bagefter.", "warn")

    m.h2("9.3 Ressourcehensyn på Pi Zero 2 W")
    m.bullets([
        "PollIntervalSeconds under 1,0 øger CPU-forbruget mærkbart uden praktisk gevinst.",
        "StatusIntervalSeconds styrer, hvor ofte browseren får opdateringer via SSE — "
        "hæv værdien, hvis mange faner er åbne samtidig.",
        "Undgå at lade dashboardet stå åbent i mange browserfaner over længere tid.",
        "Hold MaxFileSize på et realistisk niveau; meget store filer bruger både hukommelse "
        "og lang afsendelsestid.",
    ])

    # ---------------------------------------------------------------- 10
    m.h1("10. Fejlfinding", new_page=True)

    m.figure("fig12_admin_fejlfinding.png",
             "Systematisk afgrænsning fra enheden til værten.")

    m.h2("10.1 Fejlfinding på Raspberry Pi'en")

    m.h3("Trin 1 — kører tjenesterne?")
    m.code(
        "systemctl status ipr_keyboard bt_hid_ble bt_hid_agent_unified ipr-provision\n"
        "./scripts/diag_status.sh\n"
        "./scripts/diag_troubleshoot.sh          # bred kontrol af installation og miljø\n"
        "./scripts/diag_troubleshoot.sh --test-file   # opretter en testfil i pen-mappen"
    )

    m.h3("Trin 2 — ser applikationen filerne?")
    m.code(
        "mountpoint /mnt/irispen\n"
        "ls -l \"/mnt/irispen/Intern delt lagerplads/Scan text and save\"\n"
        "journalctl -u ipr_keyboard.service -f | grep -i 'Detected new file'"
    )
    m.p("Dashboardets Debug-skærm viser under Pen Files netop de filer, tjenesten faktisk "
        "kan se — det adskiller monteringsproblemer fra konfigurationsproblemer.")

    m.h3("Trin 3 — kan enheden sende?")
    m.code(
        'bt_kb_send "test"\n'
        "sudo fuser -v /run/ipr_bt_keyboard_fifo    # tomt output = ingen læser\n"
        "sudo systemctl restart bt_hid_ble.service"
    )

    m.h3("Trin 4 — Bluetooth-diagnostik")
    m.code(
        "sudo ./scripts/ble/diag_pairing.sh\n"
        "sudo ./scripts/ble/diag_bt_visibility.sh --fix\n"
        "sudo ./scripts/ble/test_pairing.sh ble\n"
        "./scripts/ble/ble_show_bt_mac_for_windows.sh"
    )

    m.h2("10.2 Den vigtigste kendte fejl: blokeret FIFO")
    m.p("Symptom: bt_kb_send, test_smoke.sh eller en overførsel stopper efter linjen "
        "“Sending text via BLE HID keyboard” og vender aldrig tilbage.", bold=True)
    m.p("Årsag: tekst blev skrevet til FIFO'en, mens ingen BLE-vært havde slået "
        "notifikationer til. Dæmonens arbejdstråd holder teksten i køen og genåbner ikke "
        "FIFO'en til læsning, før køen er tømt. Uden en læser blokerer næste skrivning i "
        "open(O_WRONLY) i det uendelige — én uafleverbar afsendelse blokerer dermed alle "
        "efterfølgende.")
    m.p("Bekræft:", bold=True)
    m.code(
        "P=$(pgrep -f bin/bt_hid_ble_daemon.py | head -1)\n"
        "for t in /proc/$P/task/*; do echo \"$(basename $t) $(sudo cat $t/wchan)\"; done\n"
        "sudo fuser -v /run/ipr_bt_keyboard_fifo"
    )
    m.p("En sund inaktiv arbejdstråd viser wait_for_partner (blokeret i open() til læsning). "
        "En blokeret tråd viser hrtimer_nanosleep, og fuser giver tomt output.")
    m.p("Afhjælpning:", bold=True)
    m.code("sudo systemctl restart bt_hid_ble.service")
    m.p("Der er indbygget beskyttelse mod tilstanden: arbejdstrådens ventetid før tømning er "
        "afgrænset af BLE_QUEUE_DRAIN_WAIT_SECS, køen af BLE_QUEUE_MAX_CHARS, "
        "bt_kb_send af BT_KB_WRITE_TIMEOUT_SECS, og send_text() afgrænser hjælperen ved "
        "30 sekunder og rapporterer “BT send timed out” i stedet for at blokere sin tråd.")

    m.h2("10.3 Eskalationsstige for Bluetooth")
    m.code(
        "sudo ./scripts/rpi-debug/dbg_bt_restart.sh       # 1: genstart stakken\n"
        "sudo ./scripts/rpi-debug/dbg_bt_soft_reset.sh    # 2: blød nulstilling\n"
        "sudo ./scripts/rpi-debug/dbg_bt_bond_wipe.sh <MAC>   # 3: slet binding\n"
        "# fjern derefter også parringen på værten, og par forfra"
    )

    m.h2("10.4 Fejlfinding på PC-siden (Windows)")
    m.table(
        ["Symptom", "Kontrollér", "Afhjælpning"],
        [
            ["Enheden vises ikke ved søgning.",
             "Kører bt_hid_agent_unified.service? Er enheden synlig?",
             "sudo ./scripts/ble/diag_bt_visibility.sh --fix og sæt enheden i "
             "parringstilstand fra dashboardet."],
            ["Parring lykkes, men intet tastatur dukker op.",
             "Enhedshåndtering → Bluetooth og HID-enheder.",
             "Fjern enheden i Windows, slet bindingen på Pi'en med dbg_bt_bond_wipe.sh, og "
             "par forfra."],
            ["Parret, men der kommer ingen tegn.",
             "Har værten slået notifikationer til? Har inputfeltet fokus?",
             "Klik i feltet, og send en testtekst fra dashboardets Debug-skærm."],
            ["Forkerte tegn, især æ, ø og å.",
             "Værtens tastaturlayout kontra det, der udsendes.",
             "Ret tastaturlayoutet på værten, så det svarer til det forventede."],
            ["Forbindelsen falder ud efter dvale.",
             "Windows' strømstyring for Bluetooth-adapteren.",
             "Fjern fluebenet ved “Tillad computeren at slukke for denne enhed for at spare "
             "strøm” i adapterens egenskaber."],
            ["Enheden findes to gange på listen.",
             "Rester efter en tidligere parring.",
             "Fjern begge poster i Windows, slet bindingen på Pi'en, og par forfra."],
        ],
        widths=[4.2, 4.8, 6.6],
        caption="Fejlmønstre på værtssiden.",
    )

    m.p("Til dybere analyse på Windows findes hjælpeskripts under scripts/tests/, herunder "
        "win_ble_capture.ps1 til opsamling af BLE-trafik og "
        "compare_ble_capture_local.py til sammenligning med enhedens egen log.")

    m.h2("10.5 Web og netværk")
    m.table(
        ["Symptom", "Sandsynlig årsag", "Afhjælpning"],
        [
            ["Dashboardet svarer ikke.",
             "Webserveren kunne ikke binde porten.",
             "journalctl -u ipr_keyboard.service | grep -i bind. Serveren forsøger fem gange "
             "med tre sekunders mellemrum og afslutter derefter processen, så systemd "
             "genstarter den."],
            ["HTTP i stedet for HTTPS.",
             "Certifikaterne kunne ikke læses.",
             "Kontrollér /etc/ipr-ssl/server.crt og server.key samt gruppen ipr-ssl på "
             "nøglefilen. Loggen indeholder da “TLS cert not accessible”."],
            ["Browseren advarer om certifikatet.",
             "CA-certifikatet er ikke installeret på klienten.",
             "Hent https://10.42.0.1/setup/ca.crt og installér det i klientens "
             "certifikatlager."],
            ["Kan ikke nå <værtsnavn>.local.",
             "mDNS er ikke tilgængeligt på nettet.",
             "Brug IP-adressen direkte, eller opret en DNS-post."],
            ["Enheden mistede netværket efter et statisk IP-skift.",
             "Forkert adresse, netmaske eller gateway.",
             "Tænd hotspottet med magneten, og ret indstillingerne via "
             "https://10.42.0.1/setup/."],
        ],
        widths=[4.2, 4.4, 7.0],
        caption="Fejlmønstre i web- og netværkslaget.",
    )

    m.h2("10.6 Indsaml en diagnosepakke")
    m.code("sudo ./scripts/rpi-debug/dbg_diag_bundle.sh")
    m.p("Skriptet samler status, logs og konfiguration i én pakke, der kan vedhæftes en "
        "fejlrapport. Gennemse indholdet for følsomme oplysninger, før du sender det videre.")

    # ---------------------------------------------------------------- 11
    m.h1("11. Test og validering", new_page=True)

    m.h2("11.1 Testniveauer")
    m.table(
        ["Niveau", "Kommando", "Hvornår"],
        [
            ["Enhedstest", "./scripts/dev_run_tests.sh eller pytest",
             "Ved enhver kodeændring, før udrulning."],
            ["Røgtest på enhed", "./scripts/test_smoke.sh",
             "Straks efter udrulning."],
            ["Ende-til-ende", "./scripts/test_e2e_systemd.sh / ./scripts/test_e2e_demo.sh",
             "Efter ændringer i afsendelsesvejen."],
            ["Hardware", "sudo bash scripts/headless/test_gpio_led_reed.sh",
             "Efter ændringer i GPIO-ledninger eller -kode."],
            ["Ny enhed", "scripts/headless/test_provision.sh",
             "Efter provisionering af en ny enhed."],
            ["Bluetooth", "sudo ./scripts/ble/test_bluetooth.sh og test_pairing.sh",
             "Efter ændringer i BLE-laget eller ved parringsproblemer."],
        ],
        widths=[3.2, 6.4, 6.0],
        mono_cols=(1,),
        caption="Testniveauer og hvornår de bruges.",
    )
    m.p("Den fulde testplan med forudsætninger, forventede resultater og "
        "hardwareafhængigheder findes i TESTING_PLAN.md i projektroden.")

    m.h2("11.2 Acceptkriterier efter installation eller opdatering")
    m.bullets([
        "De fire systemd-enheder er active.",
        "/health svarer med HTTP 200 over HTTPS.",
        "Dashboardet kan åbnes, og login virker.",
        "bt_kb_send \"test\" returnerer og teksten kommer frem på værten.",
        "En fil lagt i den overvågede mappe sendes automatisk og slettes bagefter.",
        "LED'en viser grønt, når magneten holdes tæt på en fuldt forbundet enhed.",
        "Hotspottet kan tændes og slukkes med magneten, og setup-UI'et kan nås.",
    ], numbered=True)

    # ---------------------------------------------------------------- 12
    m.h1("12. Kendte afvigelser og teknisk gæld", new_page=True)
    m.p("Følgende punkter er kendte uoverensstemmelser mellem dokumentation og kode i den "
        "nuværende udgave. De ændrer ikke produktets funktion, men er værd at kende under "
        "fejlfinding.")
    m.table(
        ["Emne", "Afvigelse", "Sådan forholder du dig"],
        [
            ["Hotspottets tilstand",
             "SERVICES.md og ARCHITECTURE.md beskriver et permanent hotspot; "
             "net_provision_hotspot.sh bruger on-demand som standard.",
             "Skriptet er gældende. Kontrollér HOTSPOT_MODE i /etc/default/ipr-provision."],
            ["Standardport",
             "AppConfig og enhedens config.json bruger 443; config.default.json angiver 8080.",
             "Læs den faktiske værdi i config.json på enheden."],
            ["Legacy-enheder",
             "bt_hid_uinput.service, ipr_backend_manager.service og bt_hid_daemon.service "
             "nævnes i ældre skripts, men leveres ikke.",
             "Behandl dem som forældede. Kør BLE-vejen."],
            ["Autentificering i API-kontrakten",
             "docs/ui/api-contract.md beskriver et API uden autentificering; "
             "implementationen kræver session til alt undtagen enkelte offentlige stier.",
             "Implementationen er gældende."],
            ["Backend-vælger",
             "Stien /etc/ipr-keyboard/backend stammer fra en tidligere uinput-baseret model.",
             "Ikke i brug. Kørslen er udelukkende BLE."],
        ],
        widths=[3.4, 6.6, 5.6],
        caption="Dokumentationsdrift, der er værd at kende.",
    )

    # ---------------------------------------------------------------- Bilag A
    m.h1("Bilag A. Kommandoreference", new_page=True)

    m.h2("Forbindelse og filoverførsel")
    m.code(
        "ssh -i ~/.ssh/ipr_rpi meibye@ipr-prod-zero2.local   # over hjemmenettet\n"
        "ssh -i ~/.ssh/ipr_rpi meibye@10.42.0.1              # over hotspottet\n"
        "ssh-copy-id -i ~/.ssh/ipr_rpi.pub meibye@ipr-prod-zero2.local\n"
        "ssh-keygen -R ipr-prod-zero2.local                  # ryd gammel værtsnøgle\n"
        "./scripts/deploy/make_payload.sh                     # pak kun det nodvendige\n"
        "scp /tmp/ipr-deploy.tgz ipr-prod:/tmp/\n"
        "ssh ipr-prod \"mkdir -p ~/dev/ipr-keyboard && \\\n"
        "  tar xzf /tmp/ipr-deploy.tgz -C ~/dev/ipr-keyboard\"\n"
        "scp <fil> ipr-prod:/tmp/                            # enkelt fil\n"
        "wsl -d Ubuntu -- rsync -avz --chmod=D755,F644 --exclude '.git' \\\n"
        "  /mnt/d/sandbox/ipr-keyboard/ ipr-prod:/home/meibye/dev/ipr-keyboard/\n"
        "git bundle create ipr-keyboard.bundle --all         # historik uden netværk"
    )

    m.h2("Status og diagnostik")
    m.code(
        "./scripts/diag_status.sh                     # samlet status (ikke som root)\n"
        "./scripts/diag_troubleshoot.sh               # bred kontrol af installationen\n"
        "./scripts/service/svc_status_services.sh     # tjenestestatus\n"
        "./scripts/service/svc_tail_all_logs.sh       # følg alle logs\n"
        "sudo ./scripts/rpi-debug/dbg_stack_status.sh # Bluetooth-stakkens tilstand\n"
        "sudo ./scripts/rpi-debug/dbg_diag_bundle.sh  # indsaml diagnosepakke"
    )

    m.h2("Tjenestestyring")
    m.code(
        "sudo systemctl restart ipr_keyboard.service\n"
        "sudo systemctl restart bt_hid_ble.service\n"
        "sudo systemctl restart bt_hid_agent_unified.service\n"
        "sudo ./scripts/service/svc_enable_services.sh\n"
        "sudo ./scripts/service/svc_disable_services.sh"
    )

    m.h2("Bluetooth")
    m.code(
        'bt_kb_send "tekst"                           # send tekst til værten\n'
        "bt_kb_send_file /sti/til/fil.txt             # send en fil\n"
        "bluetoothctl devices Connected               # forbundne værter\n"
        "sudo ./scripts/ble/diag_pairing.sh\n"
        "sudo ./scripts/ble/diag_bt_visibility.sh --fix\n"
        "sudo ./scripts/rpi-debug/dbg_bt_bond_wipe.sh <MAC>"
    )

    m.h2("Netværk og hotspot")
    m.code(
        "sudo systemctl start ipr-provision.service   # tænd hotspot\n"
        "sudo systemctl stop  ipr-provision.service   # sluk hotspot\n"
        "sudo cat /etc/ipr-hotspot.secret             # SSID og adgangskode\n"
        "sudo ./provision/07_show_info.sh             # samlede enhedsoplysninger\n"
        "sudo ./scripts/headless/net_factory_reset.sh # slet Wi-Fi-profiler\n"
        "nmcli dev status"
    )

    m.h2("Udrulning")
    m.code(
        "sudo ./scripts/deploy/deploy_full_update.sh [--install-python]\n"
        "sudo ./scripts/deploy/deploy_restart_all_services.sh\n"
        "sudo ./scripts/deploy/deploy_restart_app.sh\n"
        "sudo ./scripts/headless/gen_ipr_ssl_cert.sh --renew"
    )

    # ---------------------------------------------------------------- Bilag B
    m.h1("Bilag B. API-oversigt", new_page=True)
    m.p("Dashboardet bruger udelukkende endepunkter under /api/. Alle kræver en gyldig "
        "session, bortset fra /api/auth/login. Fejl returneres i formen "
        "{\"error\": {\"code\": …, \"message\": …}}.")
    m.table(
        ["Endepunkt", "Metode", "Formål"],
        [
            ["/api/status", "GET", "Samlet tilstand til forsiden."],
            ["/api/status/bluetooth · /pen · /transmission · /system · /health", "GET",
             "Enkeltdele af tilstanden."],
            ["/api/events · /api/events/latest", "GET", "Oversatte hændelser med filtrering."],
            ["/api/logs/raw", "GET", "Rå logudtræk."],
            ["/api/config", "GET, POST", "Læs og skriv applikationskonfiguration."],
            ["/api/network", "GET, POST", "Netværkstilstand. POST kræver administrator."],
            ["/api/actions/pairing · rescan-pen · reconnect-bluetooth", "POST",
             "Betjeningshandlinger."],
            ["/api/actions/apply-network · reboot · shutdown", "POST",
             "Kræver confirm=true. De to sidste er strømhandlinger."],
            ["/api/stream", "GET", "Server-Sent Events med løbende tilstand."],
            ["/api/debug/services · /<navn>/<handling>", "GET, POST",
             "Tjenestestatus og start/stop/genstart."],
            ["/api/debug/send-text · send-file · pen-files", "GET, POST",
             "Manuel afsendelse og indsigt i pen-mappen."],
            ["/api/auth/login · logout · me · users", "GET, POST, PATCH, DELETE",
             "Sessions- og brugeradministration."],
            ["/api/version", "GET", "Versionsoplysninger for pakke og moduler."],
        ],
        widths=[6.4, 2.6, 6.6],
        mono_cols=(0,),
        caption="Endepunkter, som dashboardet er afhængigt af.",
    )

    # ---------------------------------------------------------------- Bilag C
    m.h1("Bilag C. Ønskede fotos og skærmbilleder", new_page=True)
    m.p("Diagrammerne i manualerne er genereret sammen med dokumenterne og kan bygges om. "
        "Fotografier og skærmbilleder kan derimod ikke genereres — de skal optages eller "
        "produceres med et billedværktøj. Beskrivelserne herunder er formuleret, så de kan "
        "bruges direkte som opgavebeskrivelse til en fotograf eller som prompt til et "
        "billedgenereringsværktøj.")

    m.table(
        ["Nr.", "Ønsket billede", "Placering", "Beskrivelse"],
        [
            ["B1", "Produktfoto af enheden",
             "Brugermanual, kapitel 2",
             "Raspberry Pi Zero 2 W i sort Flirc-aluminiumskabinet, set skråt forfra på et "
             "lyst neutralt bord. Statuslampen skal være synlig gennem hullet i kabinettet "
             "og lyse grønt. Blød, ensartet belysning, ingen hårde skygger. "
             "Kabinettets to porte skal kunne skelnes."],
            ["B2", "Nærbillede af portene",
             "Brugermanual, afsnit 3.2",
             "Samme enhed set direkte fra portsiden med begge USB-porte i fokus. Tilføj "
             "efterfølgende to grafiske etiketter: “PWR — strøm” og “USB — skanner”, med "
             "pile til de respektive porte."],
            ["B3", "Magneten i brug",
             "Brugermanual, afsnit 5.2",
             "En hånd holder en lille rund neodymmagnet mod siden af kabinettet ud for "
             "lampen. Lampen lyser blåt. Nærbillede, kort dybdeskarphed."],
            ["B4", "De tre lampetilstande",
             "Brugermanual, kapitel 5",
             "Tre ens billeder af enheden side om side, hvor lampen henholdsvis lyser grønt, "
             "gult og rødt. Samme kameravinkel og belysning i alle tre, så kun farven skifter."],
            ["B5", "Windows Bluetooth-parring",
             "Brugermanual, afsnit 3.3",
             "Fire skærmbilleder fra Windows 11: (1) Indstillinger → Bluetooth og enheder, "
             "(2) dialogen Tilføj enhed, (3) enheden vist på listen under søgning, "
             "(4) bekræftelsen “Din enhed er klar til brug”. Sløret eller anonymiseret "
             "værtsnavn."],
            ["B6", "Dashboardets forside i drift",
             "Brugermanual, kapitel 6",
             "Faktisk skærmbillede af https://<værtsnavn>.local/ med status KLAR, taget i "
             "en browser i fuld bredde og igen i mobilbredde. Erstat wireframe-figuren, når "
             "billedet foreligger."],
            ["B7", "Arbejdspladsen samlet",
             "Brugermanual, kapitel 4",
             "Overbliksbillede af en typisk arbejdsplads: PC med åbent dokument, "
             "IRIS-skanneren i hånden over et papir, og enheden diskret placeret ved siden "
             "af skærmen med USB-kablet synligt."],
            ["B8", "Ledningsdiagram som fotomontage",
             "Administratormanual, afsnit 4.5",
             "Foto af GPIO-headeren med farvekodede ledninger til ben 13, 15, 16 og 18 samt "
             "GND, med indtegnede modstandsværdier 150 Ω, 150 Ω og 22 Ω. Alternativt en ren "
             "tegning baseret på skemaet i docs/hardware/gpio-wiring.md."],
            ["B9", "Reed-kontakt og LED monteret",
             "Administratormanual, afsnit 4.5",
             "Åbnet kabinet set ovenfra, hvor reed-kontaktens placering langs kabinetkanten "
             "og LED'ens monteringshul er synlige. Med henvisningsstreger og korte etiketter."],
            ["B10", "Setup-UI'ets sider",
             "Administratormanual, afsnit 5.3",
             "Skærmbilleder af https://10.42.0.1/setup/ — siderne Home, Status, WiFi og "
             "System. Hotspot-adgangskoden skal sløres."],
            ["B11", "Installation af CA-certifikat",
             "Administratormanual, afsnit 7.2",
             "Skærmbilleder af Windows' certifikatimportguide med CA-certifikatet placeret i "
             "lageret Rodnøglecentre, der er tillid til."],
        ],
        widths=[1.2, 3.4, 3.4, 8.0],
        caption="Billeder, der skal produceres eksternt, med den ønskede placering.",
    )

    m.h2("Generelle krav til billederne")
    m.bullets([
        "Mindst 1600 pixels bredde, PNG uden tab.",
        "Ensartet belysning og baggrund på tværs af produktfotos, så de fungerer som serie.",
        "Ingen identificerbare personer, netværksnavne, IP-adresser, serienumre eller "
        "adgangskoder — sløres, hvis de er uundgåelige.",
        "Skærmbilleder tages i lys tilstand med standardskalering, så teksten forbliver "
        "læsbar i trykt form.",
        "Lever filerne i docs/manuals/figures/ med filnavne på formen foto_B1_produkt.png, "
        "så de kan indsættes i genereringsskripterne.",
    ])

    m.h2("Sådan bygges manualerne om")
    m.p("Diagrammer og dokumenter genereres af skripterne i docs/manuals/_build/:")
    m.code(
        "uv run --with pillow --no-project python docs/manuals/_build/make_figures.py\n"
        "cd docs/manuals/_build\n"
        "uv run --with python-docx --no-project python build_user_manual.py\n"
        "uv run --with python-docx --no-project python build_admin_manual.py"
    )
    m.p("Indholdsfortegnelsen udfyldes først, når dokumentet åbnes i Word: markér alt med "
        "Ctrl+A og tryk F9, eller højreklik i indholdsfortegnelsen og vælg Opdatér felt.")

    m.save(OUT / "Administratormanual_IPR_Pen_Bridge.docx")


if __name__ == "__main__":
    build()
