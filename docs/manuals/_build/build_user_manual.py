"""Build the Danish user manual (Brugermanual) as a Word document."""
from __future__ import annotations

from pathlib import Path

from docx_helpers import DANGER, Manual

OUT = Path(__file__).resolve().parents[1]
VERSION = "1.1"
DATE = "11. september 2026"


def build() -> None:
    m = Manual(
        title="Brugermanual",
        subtitle="IPR Pen Bridge — fra IRIS-skanner til PC uden kabel",
        doc_id="IPR-DOC-001",
        version=VERSION,
        date=DATE,
    )
    m.toc()

    # ---------------------------------------------------------------- 1
    m.h1("1. Velkommen")
    m.p("Denne vejledning er skrevet til dig, der bruger IPR Pen Bridge i det daglige. "
        "Du behøver ikke teknisk viden for at følge den. Alt, hvad der kræver adgang til "
        "systemet eller ændringer i opsætningen, står i stedet i administratormanualen.")

    m.h2("Sådan læser du vejledningen")
    m.bullets([
        ("Kapitel 2 — ", "hvad produktet er, og hvad det bruges til."),
        ("Kapitel 3 — ", "tilslutning og første gangs parring med PC'en."),
        ("Kapitel 4 — ", "den daglige arbejdsgang."),
        ("Kapitel 5 — ", "statuslampen og magneten."),
        ("Kapitel 6 — ", "betjeningssiden i browseren, hvis du har adgang til den."),
        ("Kapitel 7 — ", "de typiske fejlsituationer og hvad du gør ved dem."),
    ])
    m.note("Ordforklaringer på de tekniske ord, du møder undervejs, finder du bagest i "
           "kapitel 9.", "info")

    # ---------------------------------------------------------------- 2
    m.h1("2. Hvad er IPR Pen Bridge?", new_page=True)
    m.p("IPR Pen Bridge er en lille boks — en Raspberry Pi Zero 2 W eller Zero W — der fungerer som "
        "bindeled mellem din IRIS-skanner og din PC.")

    m.h2("Formålet")
    m.p("Når du skanner en tekst med IRIS-skanneren, gemmer skanneren teksten som en fil "
        "inde i pennen. Normalt skal du derefter finde filen frem på en PC, åbne den og "
        "kopiere teksten det rigtige sted hen. IPR Pen Bridge fjerner de trin:")
    m.bullets([
        "Boksen opdager selv, at der er kommet en ny skanning.",
        "Den læser teksten.",
        "Den sender teksten til PC'en, som om den blev tastet ind på et tastatur.",
    ])
    m.p("For PC'en ser boksen nemlig ud som et helt almindeligt trådløst Bluetooth-tastatur. "
        "Derfor virker det i alle programmer — tekstbehandling, journalsystemer, regneark, "
        "e-mail, søgefelter — uden at der skal installeres noget på PC'en.")

    m.figure("fig01_systemoversigt.png",
             "Vejen fra papir til PC. Skanneren gemmer en tekstfil, boksen læser den og "
             "sender indholdet videre som tastetryk.")

    m.h2("Det korte overblik")
    m.table(
        ["Spørgsmål", "Svar"],
        [
            ["Hvad gør produktet?",
             "Sender skannet tekst fra IRIS-skanneren til PC'en som tastetryk."],
            ["Skal jeg installere noget på PC'en?",
             "Nej. PC'en skal blot parres med boksen én gang via Bluetooth."],
            ["Hvor havner teksten?",
             "Dér hvor markøren står på PC'en, præcis som hvis du selv skrev."],
            ["Skal boksen have netværk?",
             "Nej, ikke for at sende tekst. Netværk bruges kun til betjeningssiden."],
            ["Hvordan ser jeg, at alt virker?",
             "På statuslampen — hold magneten tæt på boksen. Se kapitel 5."],
            ["Hvor lang tid tager opstart?",
             "Ca. 1 minut fra strømmen tilsluttes, til boksen er klar."],
        ],
        widths=[5.6, 10.0],
        caption="De hyppigste spørgsmål besvaret kort.",
    )

    m.note("Boksen gemmer ikke dine skanninger. Teksten sendes videre og filen slettes "
           "normalt bagefter. Har du brug for at gemme teksten, skal du gøre det i "
           "programmet på PC'en.", "info")

    # ---------------------------------------------------------------- 3
    m.h1("3. Kom godt i gang", new_page=True)

    m.h2("3.1 Det skal du bruge")
    m.bullets([
        "IPR Pen Bridge (den lille metalboks).",
        "Strømforsyning med USB-stik til boksen.",
        "IRIS-skanneren og dens USB-kabel.",
        "Den lille magnet, der følger med boksen.",
        "En PC med Bluetooth.",
    ])

    m.h2("3.2 Tilslut udstyret")
    m.figure("fig02_tilslutning.png",
             "Tilslutningsrækkefølge: strøm først, derefter skanneren, så parring med PC'en.")

    m.p("Følg trinene i denne rækkefølge:", bold=True)
    m.bullets([
        ("Sæt strøm til boksen. ",
         "Brug PWR-porten. Lampen blinker hvidt, mens boksen starter op."),
        ("Vent ca. 1 minut. ",
         "Boksen er klar, når den hvide blinken er ophørt."),
        ("Sæt IRIS-skanneren til med USB-kablet. ",
         "Brug USB-porten på boksen — ikke PWR-porten."),
        ("Par PC'en med boksen. ",
         "Kun nødvendigt første gang. Se afsnit 3.3."),
    ], numbered=True)

    m.note("De to porte på boksen ligner hinanden. Sidder skanneren i strømporten, sker der "
           "ingenting — og lampen forbliver slukket eller rød. Byt om på stikkene, hvis du "
           "er i tvivl.", "warn")

    m.h2("3.3 Par boksen med PC'en (kun første gang)")
    m.p("Parringen skal kun laves én gang. Derefter finder PC'en og boksen selv hinanden, "
        "når de begge er tændt.")
    m.p("På en Windows-PC:", bold=True)
    m.bullets([
        "Åbn Indstillinger og vælg Bluetooth og enheder.",
        "Kontrollér at Bluetooth er slået til.",
        "Vælg Tilføj enhed og derefter Bluetooth.",
        "Vent, indtil boksen dukker op på listen. Den vises med det navn, din "
        "administrator har givet den — typisk noget med “IPR” eller “Pen Bridge”.",
        "Klik på navnet, og vent på beskeden om, at enheden er klar til brug.",
        "Åbn et tomt dokument, klik i det, og lav en prøveskanning. Teksten skal komme frem.",
    ], numbered=True)

    m.note("Bliver boksen ikke vist på listen, er den sandsynligvis ikke i parringstilstand. "
           "Kontakt din administrator — parringstilstand kan slås til fra betjeningssiden.",
           "info")

    m.h2("3.4 Den første skanning")
    m.bullets([
        "Klik i det felt eller dokument på PC'en, hvor teksten skal stå.",
        "Skan en linje tekst med IRIS-skanneren som normalt.",
        "Vent et par sekunder. Teksten skrives ind af sig selv.",
    ], numbered=True)
    m.p("Virker det, er du klar til daglig brug. Virker det ikke, så gå til kapitel 7.")

    # ---------------------------------------------------------------- 4
    m.h1("4. Daglig brug", new_page=True)

    m.h2("4.1 Den normale arbejdsgang")
    m.p("Når udstyret først er sat op, er brugen enkel:")
    m.bullets([
        "Tænd PC'en og sørg for, at boksen har strøm.",
        "Klik i det felt, hvor teksten skal ind.",
        "Skan teksten.",
        "Teksten skrives automatisk ind i feltet.",
        "Fortsæt med næste skanning.",
    ], numbered=True)
    m.p("Du skal ikke starte noget program, trykke på nogen knap eller flytte filer. "
        "Boksen arbejder af sig selv, så længe den har strøm.")

    m.h2("4.2 Hvad sker der bag kulisserne?")
    m.table(
        ["Trin", "Hvad sker der", "Hvad ser du"],
        [
            ["1", "Skanneren gemmer teksten som en fil i pennen.",
             "Skanneren kvitterer som normalt."],
            ["2", "Boksen opdager den nye fil inden for ca. 1 sekund.",
             "Ingenting — det sker i baggrunden."],
            ["3", "Boksen sender teksten til PC'en som tastetryk.",
             "Teksten dukker op ved markøren."],
            ["4", "Filen slettes fra pennen, når teksten er sendt.",
             "Pennen fyldes ikke op med gamle skanninger."],
        ],
        widths=[1.4, 7.4, 6.8],
        caption="Forløbet fra skanning til færdig tekst.",
    )

    m.h2("4.3 Gode råd")
    m.bullets([
        ("Klik først, skan bagefter. ",
         "Teksten havner altid dér, hvor markøren står. Skifter du vindue midt i en "
         "overførsel, kan teksten blive delt mellem to felter."),
        ("Skan én ting ad gangen. ",
         "Vent til teksten er skrevet færdig, før du skanner igen."),
        ("Lad boksen være tændt. ",
         "Den bruger meget lidt strøm og er klar med det samme."),
        ("Undgå at flytte boksen for langt væk. ",
         "Bluetooth rækker typisk 5–10 meter indendørs."),
        ("Kontrollér resultatet. ",
         "Skannet tekst kan indeholde læsefejl fra papiret. Læs teksten igennem, "
         "især ved tal og navne."),
    ])

    m.h2("4.4 Sluk, genstart og flytning")
    m.bullets([
        ("Kortvarig pause: ", "lad boksen være tændt. Der er ingen grund til at slukke."),
        ("Genstart: ", "tag strømmen fra, vent 10 sekunder, og sæt den til igen."),
        ("Flytning til en anden arbejdsplads: ", "tag strøm og USB-kabel fra, flyt boksen, "
         "og tilslut igen. Parringen med PC'en huskes."),
        ("Flytning til en anden PC: ", "den nye PC skal parres. Se afsnit 3.3."),
    ])
    m.note("Sluk aldrig for boksen midt i en overførsel — vent til teksten er skrevet "
           "færdig på skærmen.", "warn")

    # ---------------------------------------------------------------- 5
    m.h1("5. Statuslampen og magneten", new_page=True)
    m.p("Boksen har én lille lampe, der kan lyse i flere farver. Lampen er slukket under "
        "normal drift for at spare strøm og for ikke at forstyrre. Du vækker den ved at "
        "holde magneten tæt på boksen — så viser den status i 30 sekunder.")

    m.h2("5.1 Farvernes betydning")
    m.figure("fig03_led_farver.png",
             "Lampens farver og deres betydning.")

    m.table(
        ["Lampen viser", "Betydning", "Hvad gør du?"],
        [
            ["Hvid, hurtigt blink", "Boksen starter op.", "Vent ca. 1 minut."],
            ["Grøn, konstant", "Alt er klar.", "Ingenting — bare skan."],
            ["Gul, konstant", "Boksen kører, men PC'en er ikke forbundet.",
             "Kontrollér at PC'en er tændt og har Bluetooth slået til."],
            ["Rød, langsomt blink", "Boksen har intet netværk.",
             "Skanning virker som regel alligevel. Fortæller din administrator det, "
             "hvis betjeningssiden ikke kan nås."],
            ["Blå, konstant", "Opsætningstilstand er slået til.",
             "Slå den fra igen med magneten (3 sekunder), når du er færdig."],
            ["Slukket", "Normal drift.", "Ingenting."],
        ],
        widths=[3.8, 5.8, 6.0],
        caption="Lampens farver oversat til handling.",
    )

    m.h2("5.2 Magneten")
    m.p("Magneten er boksens eneste betjeningsknap. Hvor længe du holder den tæt på "
        "boksen, bestemmer hvad der sker.")
    m.figure("fig04_magnet_tidslinje.png",
             "Kort berøring viser status. 3 sekunder tænder eller slukker "
             "opsætningsnetværket. 10 sekunder nulstiller netværksindstillingerne.")

    m.table(
        ["Sådan gør du", "Resultat"],
        [
            ["Hold magneten tæt på og fjern den igen (under 3 sekunder)",
             "Lampen viser status i 30 sekunder."],
            ["Hold magneten på plads i 3 sekunder — lampen blinker blåt — og slip",
             "Opsætningsnetværket tændes eller slukkes."],
            ["Hold magneten på plads i 10 sekunder — lampen blinker rødt — og slip",
             "Alle gemte netværksforbindelser slettes, og boksen genstarter."],
        ],
        widths=[7.4, 8.2],
        caption="Magnetens tre funktioner.",
    )

    m.note("Nulstillingen på 10 sekunder er forbeholdt administratoren. Fortryder du "
           "undervejs, skal du blot blive ved med at holde magneten på plads, indtil "
           "lampen skifter væk fra rødt blink — handlingen udføres først, når du slipper. "
           "Er du i tvivl, så fjern magneten, inden lampen begynder at blinke rødt.",
           "danger")

    # ---------------------------------------------------------------- 6
    m.h1("6. Betjeningssiden i browseren", new_page=True)
    m.p("Boksen har en indbygget side, du kan åbne i en browser. Den er ikke nødvendig for "
        "daglig brug, men er nyttig, hvis du vil se, om alt er som det skal være. "
        "Din administrator oplyser adressen og dit brugernavn.")

    m.figure("fig05_dashboard.png",
             "Betjeningssidens forside. Status vises øverst, detaljer længere nede.")

    m.h2("6.1 De fem sider")
    m.table(
        ["Side", "Det finder du her"],
        [
            ["Forside", "Samlet status: er alt klar, eller er der noget, der kræver "
                        "opmærksomhed."],
            ["Forbindelser", "Om PC'en er forbundet, og om skanneren er fundet."],
            ["Aktivitet", "Om der sendes tekst lige nu, og hvad der er sendt for nylig."],
            ["Hændelser", "En liste i almindeligt sprog over, hvad der er sket."],
            ["Indstillinger", "Oplysninger om enheden. De fleste ændringer kræver "
                              "administratorrettigheder."],
        ],
        widths=[4.0, 11.6],
        caption="Betjeningssidens opbygning.",
    )

    m.h2("6.2 Farvemærkaten øverst")
    m.bullets([
        ("KLAR — ", "alt virker."),
        ("ARBEJDER — ", "der sendes tekst lige nu."),
        ("ADVARSEL — ", "noget kræver opmærksomhed, men tingene fungerer."),
        ("FEJL — ", "noget virker ikke. Se siden Hændelser."),
        ("OFFLINE — ", "browseren kan ikke få kontakt til boksen."),
    ])

    m.note("Knapperne Genstart og Sluk under Indstillinger spørger altid, om du er sikker, "
           "før de udføres. Brug dem kun efter aftale med din administrator.", "warn")

    # ---------------------------------------------------------------- 7
    m.h1("7. Når noget går galt", new_page=True)
    m.p("De fleste problemer skyldes ét af tre forhold: strøm, forbindelse eller markørens "
        "placering. Gå denne oversigt igennem oppefra og ned.")

    m.figure("fig06_bruger_fejlfinding.png",
             "Trinvis fejlsøgning, når teksten ikke kommer frem på PC'en.")

    m.h2("7.1 De hyppigste fejlsituationer")
    m.table(
        ["Det oplever du", "Sandsynlig årsag", "Sådan løser du det"],
        [
            ["Der sker ingenting, når jeg skanner.",
             "Boksen har ikke strøm, eller den er ikke færdig med at starte op.",
             "Kontrollér strømstikket. Hold magneten tæt på: er lampen helt død, mangler "
             "der strøm. Vent 1 minut efter tilslutning."],
            ["Lampen er gul.",
             "PC'en er ikke forbundet via Bluetooth.",
             "Tænd PC'en, kontrollér at Bluetooth er slået til, og vent ½ minut. Hjælper "
             "det ikke, så par forfra som i afsnit 3.3."],
            ["Teksten kommer i det forkerte vindue.",
             "Markøren stod et andet sted, da teksten blev sendt.",
             "Klik i det rigtige felt, før du skanner, og skift ikke vindue undervejs."],
            ["Kun en del af teksten kommer frem.",
             "Vinduet blev skiftet midt i overførslen, eller forbindelsen blev afbrudt.",
             "Slet den halve tekst, klik i feltet igen, og skan forfra."],
            ["Teksten indeholder forkerte tegn.",
             "Skanneren har læst papiret forkert, eller PC'ens tastaturlayout afviger.",
             "Skan linjen igen med roligere bevægelse. Sker det systematisk med de samme "
             "tegn (fx æ, ø, å), er det tastaturlayoutet — kontakt administratoren."],
            ["Teksten kommer meget forsinket.",
             "Boksen har mistet forbindelsen og prøver at genoprette den.",
             "Vent ½ minut. Hjælper det ikke, så tag strømmen fra boksen i 10 sekunder."],
            ["Lampen blinker rødt langsomt.",
             "Boksen har ikke netværk.",
             "Skanning virker som regel stadig. Giv administratoren besked."],
            ["Lampen lyser blåt hele tiden.",
             "Opsætningstilstand er blevet slået til ved et uheld.",
             "Hold magneten tæt på boksen i 3 sekunder og slip. Lampen skifter tilbage."],
            ["Alt så ud til at virke, men nu er alting dødt.",
             "Boksen er gået i stå.",
             "Tag strømmen fra, vent 10 sekunder, og sæt den til igen."],
        ],
        widths=[4.2, 4.6, 6.8],
        caption="Fejlsituationer, årsager og løsninger.",
    )

    m.h2("7.2 Den universelle løsning")
    m.p("Hjælper intet af ovenstående:", bold=True)
    m.bullets([
        "Tag strømmen fra boksen.",
        "Vent 10 sekunder.",
        "Sæt strømmen til igen, og vent 1 minut.",
        "Prøv en skanning.",
    ], numbered=True)

    m.h2("7.3 Hvornår skal du kontakte administratoren?")
    m.bullets([
        "Problemet vender tilbage, selv efter du har taget strømmen fra og til.",
        "Boksen kan slet ikke findes på PC'ens Bluetooth-liste.",
        "Lampen blinker rødt hver gang, du vækker den.",
        "Betjeningssiden i browseren kan ikke åbnes.",
        "Teksten indeholder systematisk de samme forkerte tegn.",
        "Du har brug for at flytte boksen til en anden PC eller et andet netværk.",
    ])
    m.p("Fortæl gerne administratoren:", bold=True)
    m.bullets([
        "Hvad lampen viste, da problemet opstod.",
        "Hvad du gjorde lige før.",
        "Om det sker hver gang, eller kun nogle gange.",
    ])

    m.note("Prøv aldrig at åbne boksen eller ændre kabler indeni. Der er ingen dele, du "
           "selv kan reparere.", "danger")

    # ---------------------------------------------------------------- 8
    m.h1("8. Sikkerhed og god praksis", new_page=True)
    m.bullets([
        ("Behandl skannet tekst som ethvert andet dokument. ",
         "Er indholdet fortroligt, gælder de samme regler, som når du selv taster det ind."),
        ("Lås din PC, når du forlader arbejdspladsen. ",
         "Boksen sender tekst til den PC, den er parret med — også hvis en anden sidder "
         "ved den."),
        ("Del ikke kodeord til betjeningssiden. ",
         "Har du selv et login, er det personligt."),
        ("Lad opsætningstilstand være slukket. ",
         "Den blå lampe betyder, at boksen udsender et trådløst netværk. Slå det fra igen, "
         "når det ikke bruges."),
        ("Meld unormal adfærd. ",
         "Sker der noget, du ikke forstår — fx tekst der dukker op af sig selv — så giv "
         "administratoren besked."),
    ])

    # ---------------------------------------------------------------- 9
    m.h1("9. Ordliste", new_page=True)
    m.table(
        ["Ord", "Betydning"],
        [
            ["Bluetooth", "Trådløs forbindelse over kort afstand. Bruges her mellem boksen "
                          "og PC'en."],
            ["Parring", "Den engangsprocedure, hvor PC'en og boksen lærer hinanden at kende."],
            ["Bro / brotog", "Kaldenavn for IPR Pen Bridge — den lille boks."],
            ["IRIS-skanner", "Den håndholdte pen, der skanner tekst fra papir."],
            ["Statuslampe (LED)", "Den lille lampe på boksen, der viser status med farver."],
            ["Reed-kontakt", "En magnetfølsom kontakt inde i boksen. Den reagerer på "
                             "magneten — der er ingen fysisk knap."],
            ["Opsætningstilstand", "En midlertidig tilstand, hvor boksen udsender sit eget "
                                   "trådløse netværk, så en administrator kan nå den."],
            ["Dashboard / betjeningsside", "Boksens side i browseren, hvor status kan ses."],
            ["Overførsel", "Det, der sker, mens teksten sendes fra boksen til PC'en."],
        ],
        widths=[4.4, 11.2],
        caption="Ord, du møder i vejledningen og på betjeningssiden.",
    )

    # ---------------------------------------------------------------- 10
    m.h1("10. Hurtig oversigt", new_page=True)
    m.p("Denne side kan printes og hænges ved arbejdspladsen.", italic=True)

    m.h2("Kom i gang")
    m.bullets([
        "Strøm i PWR-porten → vent 1 minut.",
        "Skanner i USB-porten.",
        "Klik i feltet på PC'en → skan.",
    ], numbered=True)

    m.h2("Lampens farver")
    m.table(
        ["Farve", "Betydning"],
        [
            ["Slukket", "Normal drift"],
            ["Grøn", "Alt klar"],
            ["Gul", "PC ikke forbundet"],
            ["Rød blink", "Intet netværk"],
            ["Blå", "Opsætningstilstand"],
            ["Hvid blink", "Starter op"],
        ],
        widths=[4.0, 11.6],
    )

    m.h2("Virker det ikke?")
    m.bullets([
        "Hold magneten tæt på boksen — hvad viser lampen?",
        "Står markøren i det rigtige felt?",
        "Er skanneren sat i USB-porten?",
        "Tag strømmen fra i 10 sekunder, og sæt den til igen.",
        "Hjælper det ikke: kontakt din administrator.",
    ], numbered=True)

    m.p()
    m.p("Administrator kan kontaktes på: ______________________________",
        bold=True, color=DANGER)

    m.save(OUT / "Brugermanual_IPR_Pen_Bridge.docx")


if __name__ == "__main__":
    build()
