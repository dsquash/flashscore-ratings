/**
 * Lineup Panel.jsx — ScriptUI Panel pentru After Effects
 *
 * INSTALARE (panel docabil, non-blocant):
 *   Copiaza acest fisier in:
 *   Mac:     /Applications/Adobe After Effects .../Scripts/ScriptUI Panels/
 *   Windows: C:\Program Files\Adobe\Adobe After Effects ...\Support Files\Scripts\ScriptUI Panels\
 *   Reporneste AE → apare in Window menu
 *
 * ALTERNATIV (fereastra flotanta):
 *   File → Scripts → Run Script File → select this file
 */

(function(thisObj) {

    // ── CONFIGURARE MEDIA ENCODER ─────────────────────────────────
    // Cauta presetul H.265 instalat in AME (user presets sau system presets).
    // Schimba AME_PRESET_NAME daca vrei alt preset. Lasa "" pentru fara preset.
    var AME_PRESET_NAME = "H.265 1080p High Quality";
    // ─────────────────────────────────────────────────────────────

    var DEFAULT_DIR = "C:\\Users\\marug\\Desktop\\Task #1 - FlashScore folder\\_DO NOT TOUCH_";

    // ── Detecteaza folderul scripturilor ──────────────────────────
    // Priority: 1) config file written by INSTALL_MAC.command (Mac)
    //           2) same folder as this JSX (when run as Script File)
    //           3) hardcoded Windows fallback
    var dir = "";

    // 1. Config file: ~/.flashscore_ratings (written by INSTALL_MAC.command)
    try {
        var _home = $.getenv("HOME") || $.getenv("USERPROFILE") || "";
        if (_home) {
            var _cfg = new File(_home + "/.flashscore_ratings");
            if (_cfg.exists) {
                _cfg.open("r");
                var _cfgDir = _cfg.read().replace(/[\r\n]/g, "").replace(/\\/g, "/").replace(/\/$/, "");
                _cfg.close();
                if (_cfgDir && (new File(_cfgDir + "/populate_lineup.jsx")).exists) {
                    dir = _cfgDir;
                }
            }
        }
    } catch(e) {}

    // 2. Same folder as this JSX (works via File > Scripts > Run Script File)
    if (!dir) {
        try {
            var _p = new File($.fileName).parent.fsName.replace(/\\/g, "/").replace(/\/$/, "");
            if (new File(_p + "/populate_lineup.jsx").exists) { dir = _p; }
        } catch(e) {}
    }

    // 3. Hardcoded Windows fallback
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

    // ── Helper: gaseste calea executabilului AME (Beta preferat) ─
    function _findAMEPath(isMac) {
        if (isMac) {
            // Cauta foldere AME in /Applications, sortat Beta-first
            var appsFolder = new Folder("/Applications");
            if (!appsFolder.exists) return "";
            var ameApps = appsFolder.getFiles(function(f) {
                return f instanceof Folder &&
                       f.name.toLowerCase().indexOf("adobe media encoder") >= 0;
            });
            ameApps.sort(function(a, b) {
                var aB = a.name.toLowerCase().indexOf("beta") >= 0 ? 0 : 1;
                var bB = b.name.toLowerCase().indexOf("beta") >= 0 ? 0 : 1;
                return aB - bB;
            });
            for (var _i = 0; _i < ameApps.length; _i++) {
                // Cauta .app bundle in subfolder
                var _inner = ameApps[_i].getFiles(function(f) {
                    return f instanceof Folder && f.name.slice(-4) === ".app";
                });
                if (_inner.length > 0) return _inner[0].fsName;
                return ameApps[_i].fsName;
            }
            return "";
        } else {
            // Windows: C:\Program Files\Adobe\Adobe Media Encoder*
            var adobeFolder = new Folder("C:/Program Files/Adobe");
            if (!adobeFolder.exists) return "";
            var ameFolders = adobeFolder.getFiles(function(f) {
                return f instanceof Folder &&
                       f.name.toLowerCase().indexOf("adobe media encoder") >= 0;
            });
            ameFolders.sort(function(a, b) {
                var aB = a.name.toLowerCase().indexOf("beta") >= 0 ? 0 : 1;
                var bB = b.name.toLowerCase().indexOf("beta") >= 0 ? 0 : 1;
                return aB - bB;
            });
            for (var _j = 0; _j < ameFolders.length; _j++) {
                var _exe = new File(ameFolders[_j].fsName + "/Adobe Media Encoder.exe");
                if (_exe.exists) return _exe.fsName;
                var _sf  = new File(ameFolders[_j].fsName + "/Support Files/Adobe Media Encoder.exe");
                if (_sf.exists)  return _sf.fsName;
            }
            return "";
        }
    }

    // ── Helper: cauta .epr in user presets + system presets AME ─
    function _findPreset(pname, amePath, isMac) {
        var f;
        // 1. Acelasi folder cu panelul
        f = new File(dir + "/" + pname);
        if (f.exists) return f.fsName;
        // 2. Windows user presets: AppData\Roaming\Adobe\Common\AMEPresets
        f = new File(Folder.userData.fsName + "/Adobe/Common/AMEPresets/" + pname);
        if (f.exists) return f.fsName;
        // 3. Mac user presets: ~/Library/Application Support/Adobe/Common/AMEPresets
        var _h = $.getenv("HOME") || "";
        if (_h) {
            f = new File(_h + "/Library/Application Support/Adobe/Common/AMEPresets/" + pname);
            if (f.exists) return f.fsName;
        }
        // 4. Recursiv in user AMEPresets
        var found = _findEprRecursive(
            new Folder(Folder.userData.fsName + "/Adobe/Common/AMEPresets"), pname);
        if (found) return found;
        // 5. System presets din folderul AME
        if (amePath) {
            var sysPresets = "";
            if (isMac) {
                sysPresets = amePath + "/Contents/Resources/MediaIO/presets";
            } else {
                var _tmp = amePath.replace(/\\/g, "/").replace(/\/[^\/]+\.exe$/i, "");
                if (_tmp.toLowerCase().indexOf("support files") >= 0)
                    _tmp = _tmp.replace(/\/[Ss]upport [Ff]iles$/, "");
                sysPresets = _tmp + "/MediaIO/presets";
            }
            found = _findEprRecursive(new Folder(sysPresets), pname);
            if (found) return found;
        }
        return "";
    }

    // ── Helper: adauga comp in AE Render Queue ───────────────
    function addToRenderQueue() {
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
            // Add comp to AE Render Queue
            var rqItem = app.project.renderQueue.items.add(comp);

            // Set output file to Desktop
            var outputPath = Folder.desktop.fsName.replace(/\\/g, "/") + "/" + comp.name + ".avi";
            rqItem.outputModules[1].file = new File(outputPath);

            // Open the Render Queue panel
            app.executeCommand(2161);

            statusTxt.text = "\u2713 Added to Render Queue: " + comp.name;
        } catch(e) {
            statusTxt.text = "Render Queue error \u2014 see alert.";
            alert("Could not add to Render Queue:\n" + (e.message || String(e)));
        }

        try { panel.layout.layout(true); } catch(e) {}
    }


    // ── Helper: scrie MATCH_TYPE in run.py ───────────────────
    function setMatchType(matchType) {
        var runPy = new File(dir + "/run.py");
        if (!runPy.exists) return;
        try {
            runPy.open("r");
            var content = runPy.read();
            runPy.close();
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

    // ── onClick: Run script ───────────────────────────────────
    btnRun.onClick = function() {
        var scriptName = "";
        var label      = "";
        if      (rb1.value) { scriptName = "populate_lineup.jsx";     label = "POPULATE"; }
        else if (rb2.value) { scriptName = "reset_lineup.jsx";        label = "RESET"; }
        else if (rb3.value) { scriptName = "save_template_state.jsx"; label = "SAVE STATE"; }

        if (!scriptName) return;

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

    // ── onClick: Add to Render Queue ──────────────────────────
    btnAddRQ.onClick = function() {
        addToRenderQueue();
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
