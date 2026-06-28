/* ============================================================
   score.seoryon.com — privacy page i18n (self-contained, static).
   Mirrors the main app.js language logic (priority: ?lang= >
   localStorage "seoryon_lang" > navigator) and shares the same
   storage key, so a visitor's language carries across both pages.
   DE/FR are natively localized, not literal translations.
   ============================================================ */
(() => {
  "use strict";

  // Single source of truth for the support/privacy mailbox.
  const CONTACT_EMAIL = "support@seoryon.com";

  const I18N = {
    en: {
      pp_meta_title: "Privacy Policy — Oryon AI Search Readiness Score by SEOryon",
      pp_meta_desc: "How the free score.seoryon.com tool, the /api/score backend, and the open-source oryon-score code handle your data. Plain English, no boilerplate.",
      pp_back: "← Back to Score",
      pp_back_short: "Score",

      pp_h1: "Privacy Policy",
      pp_updated: "Last updated: 26 June 2026",
      pp_intro: "This policy covers the free scoring tool at score.seoryon.com, the /api/score backend that powers it, and the open-source oryon-score Python code on GitHub. All three are made by SEOryon. Short version: there is no account, no tracking, no analytics — but the scorer does have a small server-side component, and we want to be specific about what it sees.",

      pp_s1_title: "What this site does, step by step",
      pp_s1_lead: "The score has a backend. We're naming it explicitly because most “100% local” privacy claims wouldn't apply here.",
      pp_s1_b1: "You paste a URL on score.seoryon.com. Your browser calls our serverless endpoint at /api/score with that URL as a query parameter.",
      pp_s1_b2: "The backend fetches that URL once, exactly as a browser would, and runs 27 rule-based checks on the HTML it receives. No LLMs, no third-party APIs, no enrichment services.",
      pp_s1_b3: "The score, signal results, and fixes are returned to your browser as JSON and rendered on the page. The fetch and the result are not written to a database or kept on disk.",
      pp_s1_b4: "There is no account, no login, no user profile, no usage quota, and no cookie set by score.seoryon.com.",

      pp_s2_title: "The /api/score backend",
      pp_s2_p1: "The endpoint is a stateless Python function running on Vercel's serverless runtime. For each request it:",
      pp_s2_b1: "Reads the URL you submitted from the query string.",
      pp_s2_b2: "Performs HTTP GET requests to that URL (and to its /robots.txt and /llms.txt at the same host) with a labeled User-Agent containing “OryonAISearchScore”.",
      pp_s2_b3: "Parses the HTML in memory, computes the score, and returns JSON.",
      pp_s2_b4: "Does not store the submitted URL, the fetched HTML, the computed score, your IP, or any identifier in a database we operate.",
      pp_s2_p2: "Like any web host, our serverless provider (Vercel) keeps standard, short-lived request logs — including IP address, request time, the path called, and User-Agent — to run the service and protect it from abuse. We do not use those logs to track, profile, or contact you. A short-lived edge cache may also remember a recent score for the same URL to keep the tool fast.",
      pp_s2_p3: "A practical note: the URL you submit becomes part of a request that crosses the public internet. Don't paste URLs you consider confidential (e.g. preview links protected only by obscurity). The backend will then fetch that URL itself, which means the target site sees a request from our server identifying itself as OryonAISearchScore.",

      pp_s3_title: "This website (score.seoryon.com)",
      pp_s3_lead: "This is a static page hosted on Vercel.",
      pp_s3_b1: "We do not run Google Analytics, Tag Manager, Meta Pixel, or any third-party analytics or advertising script on this page. We do not set marketing or tracking cookies. We do not fingerprint visitors.",
      pp_s3_b2: "Your language preference (English, German, French) is saved in your own browser's localStorage so the site remembers it between visits. This preference never leaves your device.",
      pp_s3_b3: "The page loads Geist, Geist Mono, and Plus Jakarta Sans from Google Fonts. Google may receive standard request metadata (IP, browser) as part of serving those fonts; we do not control that and do not use it.",
      pp_s3_b4: "Outbound links to app.seoryon.com, seoryon.com, and github.com take you to separate properties with their own privacy terms.",

      pp_s4_title: "The open-source oryon-score code",
      pp_s4_p: "The same scoring logic is open-source on GitHub under MIT. If you clone the repo and run it locally, the code fetches the URL you give it directly from your machine — nothing is sent to SEOryon, and we never see what you scored.",

      pp_s5_title: "If you create a SEOryon account",
      pp_s5_p: "This page covers the free score tool, its backend, and the open-source package only. The paid SEOryon platform at app.seoryon.com is a separate product with its own account, data handling, and privacy terms. Creating an account there is entirely optional and never required to use the score.",

      pp_s6_title: "Your data & contact",
      pp_s6_p: "Because the score backend stores nothing about you in a database we operate, there is no personal account data for us to hold, export, or delete. If you have any question about privacy — or anything you'd like clarified — reach out and we'll gladly help.",
      pp_s6_contact_label: "Contact:",

      pp_s7_title: "Changes to this policy",
      pp_s7_p: "If anything here changes — for example, if we ever decide to add lightweight, privacy-respecting analytics, or to keep scoring results for product research — we will update this page and the “last updated” date above before the change goes live. The history is visible in the open-source repository.",

      pp_footer_note: "A free GEO audit by SEOryon — your organic growth engine.",
    },

    de: {
      pp_meta_title: "Datenschutzerklärung — Oryon AI Search Readiness Score von SEOryon",
      pp_meta_desc: "Wie das kostenlose Tool auf score.seoryon.com, das Backend /api/score und der quelloffene oryon-score-Code mit deinen Daten umgehen. In Klartext, ohne Floskeln.",
      pp_back: "← Zurück zum Score",
      pp_back_short: "Score",

      pp_h1: "Datenschutzerklärung",
      pp_updated: "Zuletzt aktualisiert: 26. Juni 2026",
      pp_intro: "Diese Erklärung gilt für das kostenlose Score-Tool auf score.seoryon.com, das Backend /api/score, das es antreibt, und den quelloffenen oryon-score-Python-Code auf GitHub. Alle drei stammen von SEOryon. Kurz gesagt: Es gibt kein Konto, kein Tracking, keine Analyse-Tools – aber der Scorer hat eine kleine serverseitige Komponente, und wir wollen genau sagen, was sie sieht.",

      pp_s1_title: "Was diese Seite tut, Schritt für Schritt",
      pp_s1_lead: "Der Score hat ein Backend. Wir benennen es ausdrücklich, weil die übliche Aussage „läuft zu 100 % lokal“ hier nicht zutrifft.",
      pp_s1_b1: "Du fügst eine URL auf score.seoryon.com ein. Dein Browser ruft unseren Serverless-Endpunkt /api/score auf und gibt die URL als Query-Parameter mit.",
      pp_s1_b2: "Das Backend ruft diese URL genau einmal ab, wie ein Browser es täte, und führt 27 regelbasierte Prüfungen auf dem zurückgegebenen HTML aus. Keine LLMs, keine Drittanbieter-APIs, keine Anreicherungsdienste.",
      pp_s1_b3: "Der Score, die einzelnen Signal-Ergebnisse und die Verbesserungsvorschläge gehen als JSON an deinen Browser zurück und werden dort gerendert. Der Abruf und das Ergebnis werden nicht in einer Datenbank abgelegt und nicht auf der Festplatte gespeichert.",
      pp_s1_b4: "Es gibt kein Konto, keinen Login, kein Nutzerprofil, kein Nutzungskontingent, und score.seoryon.com setzt kein Cookie.",

      pp_s2_title: "Das Backend /api/score",
      pp_s2_p1: "Der Endpunkt ist eine zustandslose Python-Funktion auf der Serverless-Runtime von Vercel. Für jede Anfrage:",
      pp_s2_b1: "Liest sie die von dir übermittelte URL aus dem Query-String.",
      pp_s2_b2: "Führt HTTP-GET-Anfragen an diese URL sowie an /robots.txt und /llms.txt auf demselben Host aus – mit einem beschrifteten User-Agent, der „OryonAISearchScore“ enthält.",
      pp_s2_b3: "Parst das HTML im Arbeitsspeicher, berechnet den Score und liefert JSON zurück.",
      pp_s2_b4: "Speichert die übermittelte URL, das abgerufene HTML, den berechneten Score, deine IP oder irgendeine Kennung nicht in einer von uns betriebenen Datenbank.",
      pp_s2_p2: "Wie bei jedem Webhoster führt unser Serverless-Anbieter (Vercel) übliche, kurzlebige Anfrage-Logs – darunter IP-Adresse, Zeitpunkt der Anfrage, den aufgerufenen Pfad und den User-Agent –, um den Dienst auszuliefern und vor Missbrauch zu schützen. Wir nutzen diese Logs nicht, um dich zu verfolgen, zu profilieren oder zu kontaktieren. Ein kurzlebiger Edge-Cache kann zudem einen kürzlich berechneten Score für dieselbe URL kurz vorhalten, damit das Tool schnell bleibt.",
      pp_s2_p3: "Ein praktischer Hinweis: Die URL, die du übermittelst, wird Teil einer Anfrage, die über das öffentliche Internet läuft. Füge keine URLs ein, die du für vertraulich hältst (etwa Vorschau-Links, die nur durch ihre Unauffindbarkeit „geschützt“ sind). Das Backend ruft diese URL anschließend selbst ab, sodass die Zielseite eine Anfrage unseres Servers sieht, der sich als OryonAISearchScore zu erkennen gibt.",

      pp_s3_title: "Diese Website (score.seoryon.com)",
      pp_s3_lead: "Dies ist eine statische Seite, gehostet bei Vercel.",
      pp_s3_b1: "Wir betreiben auf dieser Seite weder Google Analytics noch Tag Manager noch Meta Pixel noch andere Skripte von Dritten für Analyse oder Werbung. Wir setzen keine Marketing- oder Tracking-Cookies. Wir nehmen kein Fingerprinting der Besucher vor.",
      pp_s3_b2: "Deine Sprachwahl (Englisch, Deutsch, Französisch) wird im localStorage deines Browsers gespeichert, damit die Seite sich diese Wahl über Besuche hinweg merkt. Diese Einstellung verlässt dein Gerät nie.",
      pp_s3_b3: "Die Seite lädt die Schriftarten Geist, Geist Mono und Plus Jakarta Sans über Google Fonts. Google kann beim Ausliefern dieser Schriften übliche Anfrage-Metadaten erhalten (IP, Browser); wir steuern das nicht und nutzen es nicht.",
      pp_s3_b4: "Ausgehende Links zu app.seoryon.com, seoryon.com und github.com führen zu eigenständigen Angeboten mit eigenen Datenschutzbedingungen.",

      pp_s4_title: "Der quelloffene oryon-score-Code",
      pp_s4_p: "Die gleiche Scoring-Logik ist Open Source auf GitHub unter MIT-Lizenz. Wenn du das Repo klonst und lokal ausführst, ruft der Code die von dir übergebene URL direkt von deinem Rechner ab – an SEOryon wird nichts gesendet, und wir sehen nie, was du geprüft hast.",

      pp_s5_title: "Wenn du ein SEOryon-Konto anlegst",
      pp_s5_p: "Diese Seite gilt nur für das kostenlose Score-Tool, sein Backend und das Open-Source-Paket. Die kostenpflichtige SEOryon-Plattform unter app.seoryon.com ist ein eigenständiges Produkt mit eigenem Konto, eigener Datenverarbeitung und eigenen Datenschutzbedingungen. Ein Konto dort anzulegen ist völlig freiwillig und für die Nutzung des Scores nie erforderlich.",

      pp_s6_title: "Deine Daten & Kontakt",
      pp_s6_p: "Da das Score-Backend nichts über dich in einer von uns betriebenen Datenbank speichert, gibt es keine personenbezogenen Kontodaten, die wir aufbewahren, exportieren oder löschen könnten. Wenn du eine Frage zum Datenschutz hast – oder etwas geklärt haben möchtest –, melde dich, wir helfen gern.",
      pp_s6_contact_label: "Kontakt:",

      pp_s7_title: "Änderungen an dieser Erklärung",
      pp_s7_p: "Sollte sich hier etwas ändern – falls wir uns etwa entscheiden, eine schlanke, datensparsame Analyse einzubauen oder Score-Ergebnisse für die Produktforschung aufzubewahren –, aktualisieren wir diese Seite und das Datum „Zuletzt aktualisiert“ oben, bevor die Änderung live geht. Die Versionshistorie ist im Open-Source-Repository einsehbar.",

      pp_footer_note: "Ein kostenloses GEO-Audit von SEOryon – deiner Engine für organisches Wachstum.",
    },

    fr: {
      pp_meta_title: "Politique de confidentialité — Oryon AI Search Readiness Score par SEOryon",
      pp_meta_desc: "Comment l'outil gratuit score.seoryon.com, le backend /api/score et le code open source oryon-score traitent vos données. Dit clairement, sans formules toutes faites.",
      pp_back: "← Retour au Score",
      pp_back_short: "Score",

      pp_h1: "Politique de confidentialité",
      pp_updated: "Dernière mise à jour : 26 juin 2026",
      pp_intro: "Cette politique couvre l'outil gratuit de scoring sur score.seoryon.com, le backend /api/score qui l'alimente et le code Python open source oryon-score sur GitHub. Les trois sont édités par SEOryon. En bref : pas de compte, pas de suivi, pas d'outils d'analyse — mais le scoreur comporte une petite partie côté serveur, et nous voulons dire précisément ce qu'elle voit.",

      pp_s1_title: "Ce que fait ce site, étape par étape",
      pp_s1_lead: "Le score a un backend. Nous le disons explicitement parce que la formule habituelle « 100 % local » ne s'applique pas ici.",
      pp_s1_b1: "Vous collez une URL sur score.seoryon.com. Votre navigateur appelle notre endpoint serverless /api/score en passant cette URL en paramètre.",
      pp_s1_b2: "Le backend récupère cette URL une seule fois, exactement comme le ferait un navigateur, et exécute 27 vérifications fondées sur des règles sur le HTML reçu. Aucun LLM, aucune API tierce, aucun service d'enrichissement.",
      pp_s1_b3: "Le score, les résultats par signal et les correctifs sont renvoyés au navigateur en JSON et affichés sur la page. La requête et le résultat ne sont pas écrits en base de données ni conservés sur disque.",
      pp_s1_b4: "Il n'y a pas de compte, pas de connexion, pas de profil utilisateur, pas de quota d'usage et aucun cookie n'est déposé par score.seoryon.com.",

      pp_s2_title: "Le backend /api/score",
      pp_s2_p1: "L'endpoint est une fonction Python sans état, exécutée sur le runtime serverless de Vercel. Pour chaque requête, il :",
      pp_s2_b1: "Lit l'URL que vous avez soumise depuis la chaîne de requête.",
      pp_s2_b2: "Effectue des requêtes HTTP GET vers cette URL (ainsi que vers /robots.txt et /llms.txt sur le même hôte) avec un User-Agent identifié contenant « OryonAISearchScore ».",
      pp_s2_b3: "Analyse le HTML en mémoire, calcule le score et renvoie un JSON.",
      pp_s2_b4: "Ne stocke ni l'URL soumise, ni le HTML récupéré, ni le score calculé, ni votre IP, ni le moindre identifiant dans une base que nous exploiterions.",
      pp_s2_p2: "Comme tout hébergeur, notre prestataire serverless (Vercel) conserve des journaux de requêtes standards et de courte durée — adresse IP, heure de la requête, chemin appelé, User-Agent — pour faire tourner le service et le protéger des abus. Nous ne les utilisons pas pour vous suivre, vous profiler ni vous contacter. Un cache edge de courte durée peut aussi conserver brièvement un score récent pour la même URL afin de garder l'outil rapide.",
      pp_s2_p3: "Note pratique : l'URL que vous soumettez fait partie d'une requête qui traverse l'internet public. Ne collez pas d'URL que vous considérez comme confidentielle (par exemple un lien d'aperçu protégé uniquement par son obscurité). Le backend ira alors chercher cette URL lui-même, ce qui veut dire que le site cible verra une requête venant de notre serveur, identifié comme OryonAISearchScore.",

      pp_s3_title: "Ce site (score.seoryon.com)",
      pp_s3_lead: "Il s'agit d'une page statique hébergée sur Vercel.",
      pp_s3_b1: "Nous n'utilisons sur cette page ni Google Analytics, ni Tag Manager, ni Meta Pixel, ni aucun autre script tiers d'analyse ou de publicité. Nous ne déposons pas de cookies marketing ou de suivi. Nous n'effectuons aucune empreinte numérique (fingerprinting) des visiteurs.",
      pp_s3_b2: "Votre préférence de langue (anglais, allemand, français) est enregistrée dans le localStorage de votre propre navigateur pour que le site s'en souvienne entre vos visites. Cette préférence ne quitte jamais votre appareil.",
      pp_s3_b3: "La page charge les polices Geist, Geist Mono et Plus Jakarta Sans depuis Google Fonts. Google peut recevoir, dans le cadre de la livraison de ces polices, des métadonnées de requête standards (IP, navigateur) ; nous ne les contrôlons pas et ne les utilisons pas.",
      pp_s3_b4: "Les liens sortants vers app.seoryon.com, seoryon.com et github.com mènent à des propriétés distinctes, qui ont leurs propres conditions de confidentialité.",

      pp_s4_title: "Le code open source oryon-score",
      pp_s4_p: "La même logique de scoring est open source sur GitHub, sous licence MIT. Si vous clonez le dépôt et l'exécutez en local, le code récupère l'URL que vous lui passez directement depuis votre machine — rien n'est envoyé à SEOryon, et nous ne voyons jamais ce que vous avez analysé.",

      pp_s5_title: "Si vous créez un compte SEOryon",
      pp_s5_p: "Cette page ne couvre que l'outil gratuit de score, son backend et le paquet open source. La plateforme payante SEOryon, sur app.seoryon.com, est un produit distinct, avec son propre compte, son propre traitement des données et ses propres conditions de confidentialité. Y créer un compte est entièrement facultatif et jamais nécessaire pour utiliser le score.",

      pp_s6_title: "Vos données & contact",
      pp_s6_p: "Comme le backend du score ne stocke rien sur vous dans une base que nous exploiterions, nous ne détenons aucune donnée personnelle de compte à conserver, exporter ou supprimer. Pour toute question sur la confidentialité — ou tout point à clarifier —, écrivez-nous, nous serons ravis de vous aider.",
      pp_s6_contact_label: "Contact :",

      pp_s7_title: "Modifications de cette politique",
      pp_s7_p: "Si quelque chose change ici — par exemple si nous décidons un jour d'ajouter une analyse légère et respectueuse de la vie privée, ou de conserver des résultats de score pour la recherche produit —, nous mettrons à jour cette page et la date de « dernière mise à jour » ci-dessus avant que le changement ne soit en ligne. L'historique est consultable dans le dépôt open source.",

      pp_footer_note: "Un audit GEO gratuit par SEOryon — votre moteur de croissance organique.",
    },
  };

  const SUPPORTED = ["en", "de", "fr"];
  const STORAGE_KEY = "seoryon_lang";

  const pickInitialLang = () => {
    try {
      const q = new URLSearchParams(window.location.search).get("lang");
      if (q && SUPPORTED.includes(q.toLowerCase())) return q.toLowerCase();
    } catch (_) { /* ignore */ }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED.includes(saved)) return saved;
    } catch (_) { /* localStorage may be blocked */ }
    const nav = (navigator.language || "en").slice(0, 2).toLowerCase();
    return SUPPORTED.includes(nav) ? nav : "en";
  };

  const apply = (lang) => {
    const dict = I18N[lang] || I18N.en;

    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const v = dict[el.getAttribute("data-i18n")];
      if (v != null) el.textContent = v;
    });

    if (dict.pp_meta_title) document.title = dict.pp_meta_title;
    const md = document.querySelector('meta[name="description"]');
    if (md && dict.pp_meta_desc) md.setAttribute("content", dict.pp_meta_desc);
    document.documentElement.setAttribute("lang", lang);

    document.querySelectorAll(".lang-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-lang") === lang);
    });

    try { localStorage.setItem(STORAGE_KEY, lang); } catch (_) { /* ignore */ }
  };

  document.querySelectorAll(".js-contact").forEach((el) => {
    el.textContent = CONTACT_EMAIL;
    el.setAttribute("href", "mailto:" + CONTACT_EMAIL);
  });

  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => apply(btn.getAttribute("data-lang")));
  });

  apply(pickInitialLang());
})();
