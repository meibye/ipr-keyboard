"""
Translations for the /setup/ blueprint.

Keys that contain HTML (marked with # HTML) must be rendered with | safe in templates.
All other keys are plain text and will be auto-escaped by Jinja2.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Certificate installation instructions  (HTML — use | safe)
# ---------------------------------------------------------------------------

_CERT_INSTRUCTIONS_EN = """
<p style="font-weight:700;margin:.8rem 0 .3rem">iPhone &amp; iPad (iOS / iPadOS)</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Tap <strong>Download CA Certificate</strong> above.
      Safari asks to open Settings &mdash; tap <strong>Allow</strong>
      (or dismiss and open Settings manually).</li>
  <li>In <strong>Settings</strong>, tap <strong>Profile Downloaded</strong> near the top.<br>
      <em>If it doesn&rsquo;t appear there:</em> go to
      <strong>General &rarr; VPN &amp; Device Management</strong>.</li>
  <li>Tap <strong>Install</strong> (top right), enter your passcode,
      then tap <strong>Install</strong> again to confirm.</li>
  <li>Go to <strong>Settings &rarr; General &rarr; About &rarr;
      Certificate Trust Settings</strong>.</li>
  <li>Turn on the toggle next to <em>IPR Keyboard CA</em> and
      tap <strong>Continue</strong>.</li>
</ol>
<p style="color:#888;font-size:.8rem;margin:.3rem 0 .8rem">
  Steps&nbsp;4&ndash;5 are required &mdash; without them the certificate installs
  but the browser still shows a warning.<br>
  <strong>iOS&nbsp;18.0&ndash;18.1:</strong> if Certificate Trust Settings does not
  appear after installation, update to iOS&nbsp;18.2 or later.
</p>

<p style="font-weight:700;margin:.8rem 0 .3rem">Android</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Tap <strong>Download CA Certificate</strong> above &mdash;
      the file saves to Downloads.</li>
  <li>Open <strong>Settings &rarr; Security</strong>
      (or <em>Biometrics and Security</em>).</li>
  <li>Tap <strong>Install from device storage</strong>
      (or <em>Install a certificate</em>) and choose
      <strong>CA certificate</strong>.</li>
  <li>Select the downloaded file. Name it <em>IPR Keyboard CA</em>
      when prompted.</li>
</ol>
<p style="color:#888;font-size:.8rem;margin:.3rem 0 .8rem">
  The exact menu path varies by manufacturer &mdash; search
  &ldquo;install CA certificate&rdquo; in Settings if you cannot find it.
</p>

<p style="font-weight:700;margin:.8rem 0 .3rem">Mac</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Download the file and double-click it &mdash;
      <strong>Keychain Access</strong> opens.</li>
  <li>Choose the <strong>System</strong> keychain and click
      <strong>Add</strong>.</li>
  <li>Find <em>IPR Keyboard CA</em> in the list and double-click it.</li>
  <li>Expand <strong>Trust</strong>, set <em>When using this certificate</em>
      to <strong>Always Trust</strong>, then close the window
      (enter your password to save).</li>
</ol>

<p style="font-weight:700;margin:.8rem 0 .3rem">Windows</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Download the file and double-click it.</li>
  <li>Click <strong>Install Certificate&hellip;</strong> &rarr;
      select <strong>Local Machine</strong> &rarr; Next.</li>
  <li>Choose <strong>Place all certificates in the following store</strong>,
      click <strong>Browse</strong> and select
      <strong>Trusted Root Certification Authorities</strong>.</li>
  <li>Click Next &rarr; Finish. Confirm the security prompt.</li>
</ol>
"""

_CERT_INSTRUCTIONS_DA = """
<p style="font-weight:700;margin:.8rem 0 .3rem">iPhone &amp; iPad (iOS / iPadOS)</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Tryk på <strong>Download CA-certifikat</strong> ovenfor.
      Safari beder om at åbne Indstillinger &mdash; tryk <strong>Tillad</strong>
      (eller luk og åbn Indstillinger manuelt).</li>
  <li>I <strong>Indstillinger</strong>, tryk <strong>Profil downloadet</strong>
      øverst på siden.<br>
      <em>Hvis den ikke vises:</em> gå til
      <strong>Generelt &rarr; VPN og enhedsstyring</strong>.</li>
  <li>Tryk <strong>Installer</strong> (øverst til højre), indtast din kode,
      tryk derefter <strong>Installer</strong> igen for at bekræfte.</li>
  <li>Gå til <strong>Indstillinger &rarr; Generelt &rarr; Om &rarr;
      Certifikattillidsindstillinger</strong>.</li>
  <li>Slå kontakten til for <em>IPR Keyboard CA</em> og tryk
      <strong>Fortsæt</strong>.</li>
</ol>
<p style="color:#888;font-size:.8rem;margin:.3rem 0 .8rem">
  Trin&nbsp;4&ndash;5 er påkrævet &mdash; uden dem er certifikatet installeret,
  men browseren viser stadig en advarsel.<br>
  <strong>iOS&nbsp;18.0&ndash;18.1:</strong> hvis Certifikattillidsindstillinger
  ikke vises efter installation, opdater til iOS&nbsp;18.2 eller nyere.
</p>

<p style="font-weight:700;margin:.8rem 0 .3rem">Android</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Tryk på <strong>Download CA-certifikat</strong> ovenfor &mdash;
      filen gemmes i Downloads.</li>
  <li>Åbn <strong>Indstillinger &rarr; Sikkerhed</strong>
      (eller <em>Biometri og sikkerhed</em>).</li>
  <li>Tryk <strong>Installer fra enhedslager</strong>
      (eller <em>Installer et certifikat</em>) og vælg
      <strong>CA-certifikat</strong>.</li>
  <li>Vælg den downloadede fil. Navngiv den <em>IPR Keyboard CA</em>
      når du bliver bedt om det.</li>
</ol>
<p style="color:#888;font-size:.8rem;margin:.3rem 0 .8rem">
  Den nøjagtige menusti varierer efter producent &mdash; søg efter
  &ldquo;installer CA-certifikat&rdquo; i Indstillinger, hvis du ikke kan finde det.
</p>

<p style="font-weight:700;margin:.8rem 0 .3rem">Mac</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Download filen og dobbeltklik på den &mdash;
      <strong>Nøglering</strong> åbner.</li>
  <li>Vælg <strong>System</strong>-nøgleringen og klik
      <strong>Tilføj</strong>.</li>
  <li>Find <em>IPR Keyboard CA</em> på listen og dobbeltklik på den.</li>
  <li>Udvid <strong>Tillid</strong>, sæt <em>Når du bruger dette certifikat</em>
      til <strong>Stol altid på</strong>, og luk vinduet
      (indtast din adgangskode for at gemme).</li>
</ol>

<p style="font-weight:700;margin:.8rem 0 .3rem">Windows</p>
<ol style="margin:0 0 0 1.2rem;padding:0">
  <li>Download filen og dobbeltklik på den.</li>
  <li>Klik <strong>Installer certifikat&hellip;</strong> &rarr;
      vælg <strong>Lokal maskine</strong> &rarr; Næste.</li>
  <li>Vælg <strong>Placer alle certifikater i følgende lager</strong>,
      klik <strong>Gennemse</strong> og vælg
      <strong>Betroede rodcertificeringsinstanser</strong>.</li>
  <li>Klik Næste &rarr; Udfør. Bekræft sikkerhedsprompten.</li>
</ol>
"""

# ---------------------------------------------------------------------------
# System-page cert hint rows  (HTML — use | safe)
# ---------------------------------------------------------------------------

_SYS_CERT_HINT_EN = (
    "Install once per device to remove the browser warning permanently.<br>"
    "<strong>iOS:</strong> install the profile, then enable trust in "
    "Settings &rarr; General &rarr; About &rarr; Certificate Trust Settings "
    "(iOS&nbsp;18.2+ required if it doesn&rsquo;t appear).<br>"
    "<strong>Android:</strong> Settings &rarr; Security &rarr; Install CA certificate.<br>"
    "<strong>Mac:</strong> add to System keychain, then set to Always Trust.<br>"
    "<strong>Windows:</strong> install to Trusted Root Certification Authorities.<br>"
    'Full instructions on the <a href="/setup/" style="color:#3498db">Home</a> page.'
)

_SYS_CERT_HINT_DA = (
    "Installer én gang pr. enhed for permanent at fjerne browseradvarslen.<br>"
    "<strong>iOS:</strong> installer profilen, aktiver derefter tillid i "
    "Indstillinger &rarr; Generelt &rarr; Om &rarr; Certifikattillidsindstillinger "
    "(iOS&nbsp;18.2+ kræves hvis den ikke vises).<br>"
    "<strong>Android:</strong> Indstillinger &rarr; Sikkerhed &rarr; Installer CA-certifikat.<br>"
    "<strong>Mac:</strong> tilføj til Systemkæden, angiv derefter Stol altid på.<br>"
    "<strong>Windows:</strong> installer under Betroede rodcertificeringsinstanser.<br>"
    'Fulde instruktioner på siden <a href="/setup/" style="color:#3498db">Hjem</a>.'
)

# ---------------------------------------------------------------------------
# Main translation tables
# ---------------------------------------------------------------------------

_EN: dict[str, str] = {
    # Page title
    "page_title": "IPR Keyboard – Setup",

    # Nav
    "nav_home":    "Home",
    "nav_status":  "Status",
    "nav_wifi":    "Wi-Fi",
    "nav_logs":    "Logs",
    "nav_system":  "System",
    "nav_signout": "Sign out",

    # Login
    "login_brand":          "IPR Keyboard",
    "login_title":          "Setup sign in",
    "login_username_label": "Username",
    "login_password_label": "Password",
    "login_submit":         "Sign in",
    "login_hint":           "Use the Wi-Fi password shown on the device label,\nor check https://10.42.0.1/setup/ after connecting.",
    "login_toggle_pw":      "Show or hide password",
    "login_err_invalid":    "Invalid username or password.",
    "login_err_ratelimit":  "Too many attempts — wait 60 seconds and try again.",

    # Home — Device card
    "home_device_title":   "Device",
    "home_hostname":       "Hostname",
    "home_ssh_mdns":       "SSH (mDNS)",
    "home_net_ip":         "Home network IP",
    "home_net":            "Home network",
    "home_badge_on":       "connected",
    "home_badge_off":      "not connected",

    # Home — Hotspot card
    "home_hotspot_title":  "Management Hotspot",
    "home_ssid":           "SSID",
    "home_password":       "Password",
    "home_web_ui":         "Web UI",
    "home_login_lbl":      "Login",
    "home_login_val":      "ipr  /  hotspot password above",

    # Home — Certificate card
    "home_cert_title":    "Trust Certificate",
    "home_cert_desc":     (
        "Download and install this certificate once on each device you use here. "
        "After installing it, the browser warning disappears permanently — "
        "you will not need to do this again unless you reset the device."
    ),
    "home_cert_download": "⬇ Download CA Certificate",
    "home_cert_toggle":   "How to install on your device",
    "home_cert_instructions": _CERT_INSTRUCTIONS_EN,   # HTML

    # Status
    "status_services":    "Services",
    "status_bluetooth":   "Bluetooth",
    "status_adapter":     "Adapter",
    "status_powered_on":  "powered on",
    "status_powered_off": "powered off",
    "status_active":      "active",
    "status_connected":   "connected",
    "status_paired":      "paired, not connected",
    "status_paired_devs": "Paired devices",
    "status_none":        "none",

    # Wi-Fi
    "wifi_title":        "Connect to a Wi-Fi Network",
    "wifi_desc":         (
        "Optional — saves credentials so the Pi can also reach the internet. "
        "The hotspot stays active; the Pi connects to this network after reboot."
    ),
    "wifi_network":      "Network",
    "wifi_security":     "Security",
    "wifi_sec_auto":     "Auto (WPA2)",
    "wifi_sec_open":     "Open",
    "wifi_password":     "Password",
    "wifi_placeholder":  "Wi-Fi password",
    "wifi_show":         "Show",
    "wifi_save":         "Save & Connect on Reboot",
    "wifi_rescan":       "Rescan Networks",
    "wifi_saved":        "Wi-Fi credentials saved for <strong>{ssid}</strong>. The Pi will connect after reboot. The hotspot remains active.",  # HTML

    # Logs
    "logs_title":   "Log Viewer",
    "logs_refresh": "Refresh",

    # System — Certificate card
    "sys_cert_title":          "Certificate",
    "sys_cert_expires":        "Expires",
    "sys_cert_trust":          "Trust store",
    "sys_cert_download":       "Download CA cert",
    "sys_cert_hint":           _SYS_CERT_HINT_EN,   # HTML
    "sys_cert_renew_btn":      "Renew Certificate",
    "sys_cert_renew_desc":     (
        "Generates a new 397-day certificate using the same CA. "
        "Clients that installed the CA cert do not need to reinstall it. "
        "Auto-renewal runs daily in the background."
    ),
    "sys_cert_renew_confirm":  "Renew the certificate now? The service will restart briefly.",

    # System — Actions card
    "sys_actions_title":      "System Actions",
    "sys_actions_desc":       "These actions affect the device immediately.",
    "sys_reboot_btn":         "Reboot",
    "sys_reboot_desc":        "Restarts the Pi. Reconnect to the hotspot after ~30 s.",
    "sys_reboot_confirm":     "Reboot the device now?",
    "sys_shutdown_btn":       "Shutdown",
    "sys_shutdown_desc":      "Powers off the Pi safely. Remove power after the LED stops.",
    "sys_shutdown_confirm":   "Shut down the device now?",

    # System — dynamic messages (used in route handlers)
    "msg_reboot":    "Reboot initiated. Reconnect to the hotspot in about 30 seconds.",
    "msg_shutdown":  "Shutdown initiated. Remove power after the LED stops blinking.",
    "msg_cert_ok":   "Certificate renewed. The service is restarting — this page will reload in 10 seconds.",
    "msg_cert_timeout": "Certificate renewal timed out. Check the journal for details.",
    "msg_cert_no_script": "Certificate renewal script not installed. Run install_provision_service.sh first.",
}

_DA: dict[str, str] = {
    # Page title
    "page_title": "IPR Keyboard – Opsætning",

    # Nav
    "nav_home":    "Hjem",
    "nav_status":  "Status",
    "nav_wifi":    "Wi-Fi",
    "nav_logs":    "Logfiler",
    "nav_system":  "System",
    "nav_signout": "Log ud",

    # Login
    "login_brand":          "IPR Keyboard",
    "login_title":          "Opsætning – log ind",
    "login_username_label": "Brugernavn",
    "login_password_label": "Adgangskode",
    "login_submit":         "Log ind",
    "login_hint":           "Brug Wi-Fi-adgangskoden vist på enhedsmærkaten,\neller åbn https://10.42.0.1/setup/ efter tilslutning.",
    "login_toggle_pw":      "Vis eller skjul adgangskode",
    "login_err_invalid":    "Forkert brugernavn eller adgangskode.",
    "login_err_ratelimit":  "For mange forsøg — vent 60 sekunder og prøv igen.",

    # Home — Device card
    "home_device_title":   "Enhed",
    "home_hostname":       "Værtsnavn",
    "home_ssh_mdns":       "SSH (mDNS)",
    "home_net_ip":         "Hjemmenetværks-IP",
    "home_net":            "Hjemmenetværk",
    "home_badge_on":       "forbundet",
    "home_badge_off":      "ikke forbundet",

    # Home — Hotspot card
    "home_hotspot_title":  "Administrationshotspot",
    "home_ssid":           "SSID",
    "home_password":       "Adgangskode",
    "home_web_ui":         "Web-brugerflade",
    "home_login_lbl":      "Log ind",
    "home_login_val":      "ipr  /  hotspot-adgangskoden ovenfor",

    # Home — Certificate card
    "home_cert_title":    "Stol på certifikat",
    "home_cert_desc":     (
        "Download og installer dette certifikat én gang på hver enhed du bruger her. "
        "Når det er installeret, forsvinder browseradvarslen permanent — "
        "du behøver ikke gøre dette igen, medmindre du nulstiller enheden."
    ),
    "home_cert_download": "⬇ Download CA-certifikat",
    "home_cert_toggle":   "Sådan installerer du på din enhed",
    "home_cert_instructions": _CERT_INSTRUCTIONS_DA,   # HTML

    # Status
    "status_services":    "Tjenester",
    "status_bluetooth":   "Bluetooth",
    "status_adapter":     "Adapter",
    "status_powered_on":  "tændt",
    "status_powered_off": "slukket",
    "status_active":      "aktiv",
    "status_connected":   "forbundet",
    "status_paired":      "parret, ikke forbundet",
    "status_paired_devs": "Parrede enheder",
    "status_none":        "ingen",

    # Wi-Fi
    "wifi_title":        "Opret forbindelse til et Wi-Fi-netværk",
    "wifi_desc":         (
        "Valgfrit — gemmer loginoplysninger så Pi'en også kan nå internettet. "
        "Hotspottet forbliver aktivt; Pi'en forbinder til dette netværk efter genstart."
    ),
    "wifi_network":      "Netværk",
    "wifi_security":     "Sikkerhed",
    "wifi_sec_auto":     "Auto (WPA2)",
    "wifi_sec_open":     "Åbent",
    "wifi_password":     "Adgangskode",
    "wifi_placeholder":  "Wi-Fi-adgangskode",
    "wifi_show":         "Vis",
    "wifi_save":         "Gem og forbind ved genstart",
    "wifi_rescan":       "Søg efter netværk igen",
    "wifi_saved":        "Wi-Fi-loginoplysninger gemt for <strong>{ssid}</strong>. Pi'en forbinder efter genstart. Hotspottet forbliver aktivt.",  # HTML

    # Logs
    "logs_title":   "Logviser",
    "logs_refresh": "Opdater",

    # System — Certificate card
    "sys_cert_title":          "Certifikat",
    "sys_cert_expires":        "Udløber",
    "sys_cert_trust":          "Tillidsarkiv",
    "sys_cert_download":       "Download CA-certifikat",
    "sys_cert_hint":           _SYS_CERT_HINT_DA,   # HTML
    "sys_cert_renew_btn":      "Forny certifikat",
    "sys_cert_renew_desc":     (
        "Genererer et nyt 397-dages certifikat med den samme CA. "
        "Klienter der har installeret CA-certifikatet behøver ikke installere det igen. "
        "Automatisk fornyelse kører dagligt i baggrunden."
    ),
    "sys_cert_renew_confirm":  "Forny certifikatet nu? Tjenesten genstarter et øjeblik.",

    # System — Actions card
    "sys_actions_title":      "Systemhandlinger",
    "sys_actions_desc":       "Disse handlinger påvirker enheden øjeblikkeligt.",
    "sys_reboot_btn":         "Genstart",
    "sys_reboot_desc":        "Genstarter Pi'en. Forbind igen til hotspottet efter ~30 s.",
    "sys_reboot_confirm":     "Genstart enheden nu?",
    "sys_shutdown_btn":       "Sluk",
    "sys_shutdown_desc":      "Slukker Pi'en sikkert. Fjern strømmen efter LED'en stopper.",
    "sys_shutdown_confirm":   "Sluk enheden nu?",

    # System — dynamic messages
    "msg_reboot":    "Genstart igangsat. Forbind igen til hotspottet om ca. 30 sekunder.",
    "msg_shutdown":  "Nedlukning igangsat. Fjern strømmen efter LED'en stopper.",
    "msg_cert_ok":   "Certifikat fornyet. Tjenesten genstarter — denne side genindlæses om 10 sekunder.",
    "msg_cert_timeout": "Certifikatfornyelse fik timeout. Tjek loggen for detaljer.",
    "msg_cert_no_script": "Script til certifikatfornyelse er ikke installeret. Kør install_provision_service.sh først.",
}

SUPPORTED_LANGS = ("en", "da")


def get_translations(lang: str) -> dict[str, str]:
    return _DA if lang == "da" else _EN
