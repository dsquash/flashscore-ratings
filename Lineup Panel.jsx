/**
 * Lineup Panel.jsx — ScriptUI Panel pentru After Effects
 *
 * INSTALARE (panel docabil, non-blocant):
 *   Copiaza acest fisier in:
 *   C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts\ScriptUI Panels\
 *   Reporneste AE → apare in Window menu
 *
 * ALTERNATIV (fereastra flotanta):
 *   File → Scripts → Run Script File → select this file
 */

(function(thisObj) {

    // ── CONFIGURARE MEDIA ENCODER ─────────────────────────────────
    // Numele exact al presetului din AME Preset Browser (fara extensie .epr).
    // Codul il cauta automat in folderul AMEPresets din AppData.
    // Lasa "" pentru a deschide AME fara preset.
    var AME_PRESET_NAME = "Ratings Video";
    // ─────────────────────────────────────────────────────────────

    var DEFAULT_DIR = "C:\\Users\\marug\\Desktop\\Task #1 - FlashScore folder";

    // ── Detecteaza folderul scripturilor ──────────────────────────
    var dir = "";
    try { dir = new File($.fileName).parent.fsName; } catch(e) {}
    dir = (dir || "").replace(/\\/g, "/").replace(/\/$/, "");
    if (!dir || !(new File(dir + "/populate_lineup.jsx")).exists) {
        dir = DEFAULT_DIR.replace(/\\/g, "/");
    }

    // ── Construieste UI ──────────────────────────────────────────
    var panel = (thisObj instanceof Panel)
        ? thisObj
        : new Window("palette", "Lineup Automation", undefined, {resizeable: false});

    panel.margins   = [14, 14, 14, 14];
    panel.spacing   = 8;
    panel.orientation = "column";
    panel.alignChildren = ["fill", "top"];

    // Titlu
    var titleTxt = panel.add("statictext", undefined, "LINEUP AUTOMATION");
    titleTxt.alignment = ["center", "center"];
    try { titleTxt.graphics.font = ScriptUI.newFont("dialog", "BOLD", 13); } catch(e) {}

    panel.add("panel", undefined, undefined).preferredSize = [240, 2];

    // Folder detectat
    var shortDir = dir.length > 36 ? "..." + dir.slice(-33) : dir;
    var dirLbl = panel.add("statictext", undefined, "Folder: " + shortDir);
    dirLbl.preferredSize = [240, 16];

    panel.add("panel", undefined, undefined).preferredSize = [240, 2];

    // ── Radio buttons ──────────────────────────────────────────
    var rbGrp = panel.add("panel", undefined, "Select action:");
    rbGrp.margins   = [12, 16, 12, 8];
    rbGrp.spacing   = 6;
    rbGrp.orientation = "column";
    rbGrp.alignChildren = ["left", "top"];

    var rb1 = rbGrp.add("radiobutton", undefined, "POPULATE");
    var rb2 = rbGrp.add("radiobutton", undefined, "RESET / UNPOPULATE");
    var rb3 = rbGrp.add("radiobutton", undefined, "SAVE TEMPLATE STATE");
    rb1.value = true;

    rb1.preferredSize = [220, 22];
    rb2.preferredSize = [220, 22];
    rb3.preferredSize = [220, 22];

    panel.add("panel", undefined, undefined).preferredSize = [240, 2];

    // ── Buton Run ─────────────────────────────────────────────
    var btnRun = panel.add("button", undefined, "\u25B6  Run");
    btnRun.alignment = ["fill", "center"];
    btnRun.preferredSize = [240, 36];

    // ── Buton Refresh Stats ────────────────────────────────────
    var btnRefreshStats = panel.add("button", undefined, "\u21BB  Refresh Stats");
    btnRefreshStats.alignment = ["fill", "center"];
    btnRefreshStats.preferredSize = [240, 30];

    // ── Sectiunea Render ───────────────────────────────────────
    panel.add("panel", undefined, undefined).preferredSize = [240, 2];

    var renderGrp = panel.add("panel", undefined, "Render");
    renderGrp.margins   = [12, 16, 12, 10];
    renderGrp.spacing   = 6;
    renderGrp.orientation = "column";
    renderGrp.alignChildren = ["fill", "top"];

    var btnAddRQ = renderGrp.add("button", undefined, "\u25B6\u25B6  Render");
    btnAddRQ.preferredSize = [220, 30];


    panel.add("panel", undefined, undefined).preferredSize = [240, 2];

    // Status
    var statusTxt = panel.add("statictext", undefined, "Ready.");
    statusTxt.preferredSize = [240, 16];

    // ── Helper: cauta fisier .epr recursiv in subdirectoare ───────
    function _findEprRecursive(folder, fileName) {
        if (!folder || !folder.exists) return "";
        var files = folder.getFiles("*.epr");
        for (var _fi = 0; _fi < files.length; _fi++) {
            if (files[_fi] instanceof File && files[_fi].name === fileName)
                return files[_fi].fsName;
        }
        var subFolders = folder.getFiles(function(f) { return f instanceof Folder; });
        for (var _si = 0; _si < subFolders.length; _si++) {
            var _found = _findEprRecursive(subFolders[_si], fileName);
            if (_found) return _found;
        }
        return "";
    }

    // ── Helper: gaseste comp-ul Home-Away (redenumit sau original) ─
    function findMatchComp() {
        // 1. Cauta comp redenumit: contine " - ", nu e template de player
        for (var i = 1; i <= app.project.numItems; i++) {
            var it = app.project.item(i);
            if (!(it instanceof CompItem)) continue;
            if (it.name.indexOf(" - ") < 0) continue;
            if (it.name === "Home - Away") continue;
            if (/^(home|away|Stats_|PT_)/i.test(it.name)) continue;
            return it; // primul comp "Echipa1 - Echipa2" gasit
        }
        // 2. Fallback: "Home - Away" original (inainte de populate)
        for (var j = 1; j <= app.project.numItems; j++) {
            var jt = app.project.item(j);
            if (jt instanceof CompItem && jt.name === "Home - Away") return jt;
        }
        return null;
    }

    // ── Helper: adauga comp in Adobe Media Encoder ────────────
    function addToMediaEncoder() {
        var comp = findMatchComp();
        if (!comp) {
            if (app.project.activeItem instanceof CompItem) {
                comp = app.project.activeItem;
            } else {
                statusTxt.text = "ERROR: match comp not found.";
                alert("Could not find the match comp (e.g. 'Dortmund - Bayern').\n" +
                      "Run POPULATE first, or select the comp manually in AE.");
                return;
            }
        }

        try {
            if (!app.encoder) {
                alert("Adobe Media Encoder is not available.\n" +
                      "Make sure AME is installed and the version matches AE.");
                return;
            }

            // ── Cauta preset-ul .epr dupa nume ───────────────────
            var presetPath = "";
            if (AME_PRESET_NAME !== "") {
                var _pname = AME_PRESET_NAME + ".epr";
                // 1. Acelasi folder cu panelul
                var _f1 = new File(dir + "/" + _pname);
                if (_f1.exists) { presetPath = _f1.fsName; }
                // 2. AppData\Roaming\Adobe\Common\AMEPresets (Windows)
                if (!presetPath) {
                    var _f2 = new File(Folder.userData.fsName + "/Adobe/Common/AMEPresets/" + _pname);
                    if (_f2.exists) { presetPath = _f2.fsName; }
                }
                // 3. Cauta recursiv in AMEPresets (subdirectoare — preset-uri organizate pe foldere)
                if (!presetPath) {
                    var _ameRoot = new Folder(Folder.userData.fsName + "/Adobe/Common/AMEPresets");
                    presetPath = _findEprRecursive(_ameRoot, _pname);
                }
                if (!presetPath) {
                    statusTxt.text = "Preset '" + AME_PRESET_NAME + "' not found, adding without preset...";
                }
            }

            // Porneste AME daca nu e deschis deja
            app.encoder.launchEncoder();
            // Adauga in coada AME
            app.encoder.encodeComp(comp, presetPath, "");
            statusTxt.text = "\u2713 AME: " + comp.name + (presetPath ? " [" + AME_PRESET_NAME + "]" : " [no preset]");
        } catch(e) {
            var msg = (e.message || String(e));
            statusTxt.text = "AME ERROR \u2014 " + msg;
            alert("Media Encoder error:\n" + msg);
        }

        try { panel.layout.layout(true); } catch(e) {}
    }

    // ── onClick: Run script ───────────────────────────────────
    // ── Helper: scrie MATCH_TYPE in run.py ───────────────────
    function setMatchType(matchType) {
        var runPy = new File(dir + "/run.py");
        if (!runPy.exists) return; // run.py optional
        try {
            runPy.open("r");
            var content = runPy.read();
            runPy.close();
            // Inlocuieste linia MATCH_TYPE = "..." cu valoarea selectata
            var updated = content.replace(
                /^MATCH_TYPE\s*=\s*["'][^"']*["']/m,
                'MATCH_TYPE = "' + matchType + '"'
            );
            if (updated !== content) {
                runPy.open("w");
                runPy.write(updated);
                runPy.close();
            }
        } catch(e) {}
    }

    btnRun.onClick = function() {
        var scriptName = "";
        var label      = "";
        if      (rb1.value) { scriptName = "populate_lineup.jsx";     label = "POPULATE"; }
        else if (rb2.value) { scriptName = "reset_lineup.jsx";        label = "RESET"; }
        else if (rb3.value) { scriptName = "save_template_state.jsx"; label = "SAVE STATE"; }

        if (!scriptName) return;

        // (MATCH_TYPE e setat din launcher, nu din AE)

        var fScript = new File(dir + "/" + scriptName);
        if (!fScript.exists) {
            statusTxt.text = "ERROR: script not found!";
            alert("Script not found: " + scriptName + "\n\nCurrent folder:\n" + dir);
            return;
        }

        statusTxt.text = "Running: " + label + "...";
        try { panel.layout.layout(true); } catch(e) {}

        try {
            $.global.__LINEUP_SCRIPTS_DIR__ = dir;
            $.evalFile(fScript);
            statusTxt.text = label + " \u2014 done.";
        } catch(e) {
            var msg = (e.message || String(e));
            if (e.line) msg += " (linie " + e.line + ")";
            statusTxt.text = "ERROR \u2014 see alert.";
            alert("Error in " + label + ":\n" + msg);
        }

        try { panel.layout.layout(true); } catch(e) {}
    };

    // ── onClick: Refresh Stats ─────────────────────────────────
    btnRefreshStats.onClick = function() {
        var scriptPath    = dir + "/refresh_stats.py";
        var refreshJsx    = dir + "/refresh_comps.jsx";
        var summaryPath   = dir + "/flashscore_output/last_refresh_summary.txt";

        if (!(new File(scriptPath)).exists) {
            alert("refresh_stats.py was not found in:\n" + dir);
            return;
        }

        // ── Step 1: run Python scraper to update data.json ────────
        statusTxt.text = "Refreshing stats from Flashscore...";
        try { panel.layout.layout(true); } catch(e) {}

        var winPath = scriptPath.replace(/\//g, "\\");
        system.callSystem('cmd /c python "' + winPath + '" >nul 2>&1');

        // ── Step 2: read and show summary ─────────────────────────
        var sf = new File(summaryPath);
        var summaryText = "";
        if (sf.exists) {
            sf.encoding = "UTF-8";
            sf.open("r");
            summaryText = sf.read();
            sf.close();
        }

        if (summaryText) {
            alert("REFRESH STATS\n\n" + summaryText);
        }

        // ── Step 3: update AE compositions ────────────────────────
        var fJsx = new File(refreshJsx);
        if (fJsx.exists) {
            statusTxt.text = "Updating compositions...";
            try { panel.layout.layout(true); } catch(e) {}
            try {
                $.global.__LINEUP_SCRIPTS_DIR__ = dir;
                $.evalFile(fJsx);
                statusTxt.text = "Refresh Stats \u2014 done.";
            } catch(e) {
                statusTxt.text = "ERROR updating comps \u2014 see alert.";
                alert("Error in refresh_comps.jsx:\n" + (e.message || String(e)));
            }
        } else {
            statusTxt.text = "Refresh Stats \u2014 done (comps not updated).";
            alert("refresh_comps.jsx not found.\nStats were updated in data.json but compositions were not refreshed.");
        }

        try { panel.layout.layout(true); } catch(e) {}
    };

    // ── onClick: Add to Media Encoder ─────────────────────────
    btnAddRQ.onClick = function() {
        addToMediaEncoder();
    };


    // ── Footer ────────────────────────────────────────────────
    var footerGrp = panel.add("group");
    footerGrp.alignment = ["fill", "bottom"];
    footerGrp.margins = [0, 6, 0, 2];
    var footerTxt = footerGrp.add("statictext", undefined,
        "Reach out to Marian Grosu for any problem.");
    footerTxt.alignment = ["center", "center"];
    footerTxt.justify = "center";

    // ── Afiseaza ──────────────────────────────────────────────
    panel.layout.layout(true);
    if (panel instanceof Window) {
        panel.center();
        panel.show();
    }

})(this);
