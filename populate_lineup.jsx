/**
 * populate_lineup.jsx — After Effects lineup auto-populator
 * ════════════════════════════════════════════════════════════
 * Pune scriptul in acelasi folder cu proiectul .aep
 * Ruleaza: File -> Scripts -> Run Script File
 *
 * Structura asteptata in proiect:
 *   MAIN COMP (3840x2160)
 *     ├── "Home Team"     text layer
 *     ├── "Away Team"     text layer
 *     ├── "Score"         text layer
 *     └── "MASTER CTRL"  null layer
 *
 *   home_player_01 (470x400)
 *     ├── "Stats"          comp (470x400)
 *     │     └── "CTRL"     null cu efecte: Note, Goal, Change,
 *     │                    Yellow Card, Red Card, Star,
 *     │                    Multiple Goals, How many goals
 *     └── "Player Template" comp (660x644)
 *           ├── "Player Photo.png"  footage
 *           ├── "1"                 text (numar)
 *           └── "Name"             text (nume)
 *
 * Orientare teren:
 *   Home: portar stanga → atacanti dreapta
 *   Away: atacanti stanga → portar dreapta
 *   Rezerve: rand orizontal sub teren
 * ════════════════════════════════════════════════════════════
 */

// ── CONFIGURARE ──────────────────────────────────────────────
var TEMPLATE_COMP     = "home_player_01";
var MAIN_COMP_NAME    = "MAIN COMP";
var LAYER_HOME_TEAM   = "Home Team";
var LAYER_AWAY_TEAM   = "Away Team";
var LAYER_SCORE       = "Score";
var LAYER_HOME_LOGO   = "Home Logo";        // layer imagine in MAIN COMP
var LAYER_AWAY_LOGO   = "Away Logo";        // layer imagine in MAIN COMP

// Compozitii rating medie echipe
var HOME_RATING_COMP  = "Home Rating";      // comp separat din proiect
var AWAY_RATING_COMP  = "Away Rating";      // comp separat din proiect
var HOME_RATING_LAYER = "Home - Rating";    // layer cu slider in Home Rating comp
var AWAY_RATING_LAYER = "Away - Rating";    // layer cu slider in Away Rating comp (fallback: "Home - Rating")

// Comp "Home - Away" redenumit cu echipele reale
var MATCH_NAME_COMP   = "Home - Away";      // numele din template — va fi redenumit

// Change Sub.png se afla in Stats comp (hidden by default in template)
var STATS_CHANGE_IMG     = "Change.png";        // layer imagine in Stats comp
var STATS_CHANGE_SUB_IMG = "Change Sub.png";    // layer imagine in Stats comp (pt rezerve)

var STATS_LAYER       = "Stats";
var PT_LAYER          = "Player Template";
var CTRL_LAYER        = "CTRL";

var PT_PHOTO          = "Player Photo.png";
var PT_NUMBER         = "1";
var PT_NAME           = "Name";

var FX = {
    note:          "Note",
    goal:          "Goal",
    change:        "Change",
    yellowCard:    "Yellow Card",
    redCard:       "Red Card",
    star:          "Star",
    multipleGoals: "Multiple Goals",
    howManyGoals:  "How many goals"
};

// Teren in MAIN COMP (pixeli) — rezolutie 2700x2160
// Colturi masurate in AE: TL(203, 208.5)  BL(202.6, 1572.4)
//                          TR(2405.5, 208.9)  BR(2405.5, 1572.2)
var FIELD_LEFT   = 203;
var FIELD_TOP    = 208.5;
var FIELD_WIDTH  = 2202.5;   // 2405.5 - 203
var FIELD_HEIGHT = 1363.9;   // 1572.4 - 208.5

// Distanta sub teren pentru rezerve (px sub marginea de jos a terenului)
var SUB_OFFSET_Y = 60;

// Scala vizuala a cardurilor in MAIN COMP (daca template-ul e scalat in AE).
var CARD_SCALE    = 0.50;
var CARD_W_VISUAL = 470 * CARD_SCALE;
var CARD_GAP      = 20;
var CARD_STEP     = CARD_W_VISUAL + CARD_GAP;

// Rezerve — scala dinamica in functie de numarul maxim de subs ale unei echipe:
//   <= 3 subs → 100%  |  4 subs → 90%  |  5+ subs → 80%
// SUB_SCALE_DEFAULT este folosit doar ca fallback; valoarea reala e calculata dinamic.
var SUB_SCALE_DEFAULT = 90;
var SUB_CARD_STEP     = 250;   // distanta centru-la-centru (aceeasi indiferent de scala)

// Offset fata de centrul canvas-ului pana la cea mai apropiata rezerva
// (home spre stanga, away spre dreapta)
var SUB_CENTER_GAP = 130;

// Distanta minima centru-la-centru intre jucatorii din aceeasi linie (anti-overlap)
var MIN_Y_STEP    = CARD_W_VISUAL + CARD_GAP;  // 235 + 20 = 255px

// Compresia verticala a jucatorilor pe teren.
// HOME si AWAY trebuie sa fie egale ca linia de jos sa se alinieze.
var HOME_Y_SCALE = 0.96;
var AWAY_Y_SCALE = 0.96;

// Compresie Y pentru jucatorii de camp (nu GK, nu subs) — fata de centrul terenului.
// Valori mai mari = linia de jos coboara mai mult spre marginea terenului.
var HOME_OUTFIELD_Y_COMPRESS = 0.91;
var AWAY_OUTFIELD_Y_COMPRESS = 0.91;

// Padding X de la marginea terenului/mijloc pana la cel mai exterior jucator.
var FIELD_X_PAD = 45;

// Micro-ajustare verticala pentru portari (index 0). Pozitiv = mai jos pe ecran.
// Calculat din pozitia masurata in AE: Y=890.278 (centrul vertical al terenului)
var GK_Y_NUDGE  = 82;

// Portarii folosesc un Y_SCALE separat (original 0.88) ca sa ramana la pozitia masurata.
// Jucatorii de camp folosesc HOME_Y_SCALE/AWAY_Y_SCALE (0.96).
var GK_Y_SCALE  = 0.88;

// Limita superioara Y pentru jucatorii de camp (nu GK, nu subs).
// Niciun jucator nu urca mai sus de aceasta valoare (masurat in AE: Y=449.244).
var MIN_PLAYER_Y = 449.244;

// Decalaj X suplimentar pentru home team (muta toti jucatorii home spre centru/dreapta).
var HOME_X_SHIFT = 60;

// Decalaj X suplimentar pentru portarul home (home_player_01). Negativ = mai spre stanga.
// Calculat din pozitia masurata in AE: X=202.447 (marginea stanga a terenului)
var HOME_GK_X_NUDGE = -106;

// Decalaj X suplimentar pentru portarul away. Pozitiv = mai spre dreapta.
// Simetric cu home: impinge portarul away la marginea dreapta a terenului (X≈2405.5)
var AWAY_GK_X_NUDGE = 45;

// Decalaj X pentru atacanti + mij atacanti away (position_top < 48) — linia din fata.
var AWAY_FW_MID_X_SHIFT = 120;
// Decalaj X pentru mij defensivi away (48 <= position_top < 68) — linia din spate.
var AWAY_DMF_X_SHIFT    = 40;

// Shift spre STANGA pentru home (valori negative = stanga).
// Fundasi (pos_top>=68): shift mic.
// Mijlocasi + Atacanti (pos_top<68): impreuna, shift usor mai mare.
var HOME_DEF_X_SHIFT     = -40;   // fundasi (position_top >= 68)
var HOME_MID_ATK_X_SHIFT = -50;   // mijlocasi + atacanti (position_top < 68)

// Limite X pentru rezerve (din masuratori AE)
var SUB_HOME_LEFT_LIMIT  = 307.693;   // home subs nu trec mai la stanga de acesta
var SUB_AWAY_RIGHT_LIMIT = 2374.25;   // away subs nu trec mai la dreapta de acesta

// Spacing jucatori bazat pe lungimea numelui afisat
var CHARS_PER_CARD = 14;              // maxim caractere la CARD_W_VISUAL
var PX_PER_CHAR    = CARD_W_VISUAL / CHARS_PER_CARD;  // ~16.8 px per caracter
// ─────────────────────────────────────────────────────────────


// Counter global — creste cu 1 la fiecare jucator adaugat (home XI, away XI, home subs, away subs)
// Folosit pentru stagger-ul Stats si pentru marker-ul pe comp
var playerGlobalIdx = 0;

(function () {

    // ── Detecteaza folderul scripturilor ─────────────────────
    // Prioritate: variabila injectata de panel → $.fileName → prompt manual
    var dir = "";
    try {
        if (typeof $.global.__LINEUP_SCRIPTS_DIR__ !== "undefined" && $.global.__LINEUP_SCRIPTS_DIR__)
            dir = $.global.__LINEUP_SCRIPTS_DIR__;
    } catch(e) {}
    if (!dir) {
        try { dir = new File($.fileName).parent.fsName; } catch(e) {}
    }
    if (!dir) {
        var _fb = Folder.selectDialog("Selecteaza folderul cu scripturile (Task #1)");
        if (!_fb) return;
        dir = _fb.fsName;
    }
    dir = dir.replace(/\\/g, "/").replace(/\/$/, "");

    var dataPath  = dir + "/flashscore_output/data.json";
    var imagesDir = dir + "/flashscore_output/images/";

    // ── Log de debug (scris la fiecare rulare) ───────────────
    var _logFile = new File(dir + "/lineup_debug.txt");
    function dbg(msg) {
        try {
            _logFile.encoding = "UTF-8";
            _logFile.open("a");
            _logFile.writeln("[" + (new Date()).toLocaleTimeString() + "] " + msg);
            _logFile.close();
        } catch(e2) {}
    }
    dbg("=== POPULATE START === dir=" + dir);

    var jf = new File(dataPath);
    if (!jf.exists) {
        dbg("EROARE: data.json negasit la " + dataPath);
        alert("File not found:\n" + dataPath +
              "\n\nRun run.py first to generate the data.");
        return;
    }
    jf.open("r");
    var data = JSON.parse(jf.read());
    jf.close();
    dbg("data.json citit OK");

    var match = data.match;

    // ── Gaseste Main Comp ────────────────────────────────────
    var mainComp = findCompByName(MAIN_COMP_NAME);
    if (!mainComp) mainComp = app.project.activeItem;
    if (!mainComp || !(mainComp instanceof CompItem)) {
        alert("Please select MAIN COMP and try again.");
        return;
    }

    // ── Find template ────────────────────────────────────────
    var tplComp = findCompByName(TEMPLATE_COMP);
    if (!tplComp) {
        alert("Template comp not found: " + TEMPLATE_COMP);
        return;
    }

    // ── Protejeaza template de conflicte de nume ─────────────
    // Prima rulare: home_player_01 este template-ul.
    // Urmatoarele rulari: home_player_01 ar putea fi comp-ul lui Pena
    // din rularea anterioara. Redenumim temporar template-ul.
    var PROTECTED_NAME = "__TPL_PROTECTED__";
    tplComp.name = PROTECTED_NAME;

    app.beginUndoGroup("Populate FlashScore Lineup");

    // ── Match info ───────────────────────────────────────────
    setTxt(mainComp, LAYER_HOME_TEAM, match.home_team);
    setTxt(mainComp, LAYER_AWAY_TEAM, match.away_team);

    // ── Logo-uri ─────────────────────────────────────────────
    replaceImgLayer(mainComp, LAYER_HOME_LOGO, imagesDir + "home_logo.png");
    replaceImgLayer(mainComp, LAYER_AWAY_LOGO, imagesDir + "away_logo.png");

    // ── Average ratings → slider in compozitiile Home Rating / Away Rating ──
    if (match.home_avg_rating)
        setRatingSlider(HOME_RATING_COMP, HOME_RATING_LAYER, parseFloat(match.home_avg_rating));
    if (match.away_avg_rating)
        setRatingSlider(AWAY_RATING_COMP, AWAY_RATING_LAYER, parseFloat(match.away_avg_rating));

    // ── Redenumeste comp-ul "Home - Away" cu echipele reale ──
    var matchNameComp = findCompByName(MATCH_NAME_COMP);
    if (!matchNameComp) {
        for (var _i = 1; _i <= app.project.numItems; _i++) {
            var _it = app.project.item(_i);
            if (_it instanceof CompItem &&
                _it.name.indexOf(" - ") > 0 &&
                _it.name !== MATCH_NAME_COMP &&
                !/^(home|away|Stats_|PT_)/.test(_it.name)) {
                matchNameComp = _it; break;
            }
        }
    }
    if (matchNameComp) matchNameComp.name = match.home_team + " - " + match.away_team;

    var scoreStr  = match.home_score + "-" + match.away_score;
    var scoreLyr  = findLayerIn(mainComp, LAYER_SCORE);
    if (scoreLyr) {
        var prop = scoreLyr.property("Source Text");
        try { if (prop.expressionEnabled) prop.expressionEnabled = false; } catch(e) {}
        if (!prop.numKeys || prop.numKeys === 0) {
            var td = prop.value;
            td.text = String(scoreStr);
            try { prop.setValue(td); } catch(e1) {}
        }
    } else {
        alert("WARNING: Layer '" + LAYER_SCORE + "' was not found in MAIN COMP.\n" +
              "Make sure the score text layer is named exactly: " + LAYER_SCORE);
    }

    // ── Sterge layerele vechi ────────────────────────────────
    clearOldLayers(mainComp);

    // ── Y pentru rezerve ─────────────────────────────────────────────
    var subY = FIELD_TOP + FIELD_HEIGHT + SUB_OFFSET_Y;

    // ── Scala dinamica rezerve ────────────────────────────────────────
    // Referinta = nr maxim de subs intre cele doua echipe
    var homeSubs = data.home.substitutes.length;
    var awaySubs = data.away.substitutes.length;
    var refSubs  = Math.max(homeSubs, awaySubs);
    var dynamicSubScale = (refSubs <= 3) ? 100
                        : (refSubs === 4) ? 90
                        : 75;  // 5+

    // Constante pentru formula X (GK=88, atacanti=18, range=70)
    var X_GK_TOP    = 88;
    var X_ATK_TOP   = 18;
    var X_RANGE     = X_GK_TOP - X_ATK_TOP; // 70
    var HOME_X_FROM = FIELD_LEFT + FIELD_X_PAD;
    var HOME_X_TO   = FIELD_LEFT + FIELD_WIDTH / 2 - FIELD_X_PAD;
    var AWAY_X_FROM = FIELD_LEFT + FIELD_WIDTH / 2 + FIELD_X_PAD;
    var AWAY_X_TO   = FIELD_LEFT + FIELD_WIDTH - FIELD_X_PAD;

    // ── Home XI ──────────────────────────────────────────────
    data.home.players.sort(function(a, b) {
        if (a.position_top !== b.position_top) return b.position_top - a.position_top;
        return b.position_left - a.position_left;
    });

    var homeCenterY = FIELD_TOP + FIELD_HEIGHT / 2;

    // Pre-calculeaza Y pentru toti jucatorii home
    for (var i = 0; i < data.home.players.length; i++) {
        var p  = data.home.players[i];
        if (i === 0) {
            // Portarul: formula originala cu GK_Y_SCALE (pozitia masurata)
            var gkPy = FIELD_TOP + ((100 - p.position_left) / 100) * FIELD_HEIGHT * GK_Y_SCALE;
            p._py = gkPy + GK_Y_NUDGE;
        } else {
            var py = FIELD_TOP + ((100 - p.position_left) / 100) * FIELD_HEIGHT * HOME_Y_SCALE;
            p._py = homeCenterY + (py - homeCenterY) * HOME_OUTFIELD_Y_COMPRESS;
            if (p._py < MIN_PLAYER_Y) p._py = MIN_PLAYER_Y;
        }
    }
    // Rezolva suprapunerile in linii (skip GK la index 0)
    resolveOverlaps(data.home.players.slice(1));
    // Clamp dupa redistribute (resolveOverlaps poate muta jucatori)
    for (var _ci = 1; _ci < data.home.players.length; _ci++) {
        if (data.home.players[_ci]._py < MIN_PLAYER_Y)
            data.home.players[_ci]._py = MIN_PLAYER_Y;
    }
    // Distribuie uniform Y in cadrul fiecarei coloane home (Di Marco → Dumfries egale)
    evenlySpaceColumns(data.home.players.slice(1));

    // Retine Y-ul maxim al jucatorilor home (linia de jos) pentru alinierea away
    var homeMaxY = 0;
    for (var _hm = 1; _hm < data.home.players.length; _hm++) {
        if (data.home.players[_hm]._py > homeMaxY) homeMaxY = data.home.players[_hm]._py;
    }

    // Limita X pentru home: atacantii nu trec de HOME_X_MAX
    // HOME_X_MAX = mijlocul terenului minus un pad (atacantii home nu intra in jumatatea away)
    var HOME_X_MAX = FIELD_LEFT + FIELD_WIDTH / 2 - 80;

    for (var i = 0; i < data.home.players.length; i++) {
        var p     = data.home.players[i];
        var n     = pad(i + 1);
        var imgIdx = (p.index !== undefined) ? (p.index + 1) : (i + 1);
        var normX = (X_GK_TOP - p.position_top) / X_RANGE; // 0=GK, 1=atacant
        var px    = HOME_X_FROM + normX * (HOME_X_TO - HOME_X_FROM) + HOME_X_SHIFT;
        if (i === 0) {
            px += HOME_GK_X_NUDGE;
        } else {
            // Shift tiered spre stanga: mij+att impreuna, fundasi separat
            if (p.position_top < 68) px += HOME_MID_ATK_X_SHIFT;  // mijlocasi + atacanti
            else                     px += HOME_DEF_X_SHIFT;        // fundasi
            // Limiteaza atacantii sa nu depaseasca mijlocul terenului
            if (px > HOME_X_MAX) px = HOME_X_MAX;
        }
        buildPlayer(mainComp, tplComp, "home_player_" + n, p,
            imagesDir + "home_player_" + imgIdx + ".png",
            px, p._py, playerGlobalIdx);
        playerGlobalIdx++;
    }

    // ── Home Subs — de la centrul canvas-ului spre stanga ──
    var canvasCenterX = FIELD_LEFT + FIELD_WIDTH / 2;
    var lastHomeSubGlobalIdx = -1;
    if (homeSubs > 0) {
        var hRightmost = canvasCenterX - SUB_CENTER_GAP;
        var homeSubBaseIdx = playerGlobalIdx;
        var homeSubStep = SUB_CARD_STEP;
        if (homeSubs > 1) {
            var _hLeftmost = hRightmost - (homeSubs - 1) * homeSubStep;
            if (_hLeftmost < SUB_HOME_LEFT_LIMIT) {
                homeSubStep = (hRightmost - SUB_HOME_LEFT_LIMIT) / (homeSubs - 1);
            }
        }
        for (var s = 0; s < homeSubs; s++) {
            var sub = data.home.substitutes[s];
            var n   = pad(s + 1);
            var px  = hRightmost - (homeSubs - 1 - s) * homeSubStep;
            // Stats in ordine INVERSA: sub_04 apare prima (idx mic), sub_01 apare ultima (idx mare)
            var subGlobalIdx = homeSubBaseIdx + (homeSubs - 1 - s);
            buildPlayer(mainComp, tplComp, "home_sub_" + n, sub,
                imagesDir + "home_sub_" + (s + 1) + ".png",
                px, subY, subGlobalIdx, dynamicSubScale, true);
        }
        playerGlobalIdx += homeSubs;
        lastHomeSubGlobalIdx = homeSubBaseIdx + homeSubs - 1;
    }

    // ── Delay 2s intre ultimul home_sub si primul away_player ────────────
    playerGlobalIdx++;

    // ── Away XI ──────────────────────────────────────────────
    var awayCenterY = FIELD_TOP + FIELD_HEIGHT / 2;

    // Limita X pentru away: atacantii nu trec de AWAY_X_MIN
    var AWAY_X_MIN = FIELD_LEFT + FIELD_WIDTH / 2 + 80;

    // Pre-calculeaza Y pentru toti jucatorii away
    for (var j = 0; j < data.away.players.length; j++) {
        var q  = data.away.players[j];
        if (j === 0) {
            // Portarul: formula originala cu GK_Y_SCALE (pozitia masurata)
            var gkPy = FIELD_TOP + (q.position_left / 100) * FIELD_HEIGHT * GK_Y_SCALE;
            q._py = gkPy + GK_Y_NUDGE;
        } else {
            var py = FIELD_TOP + (q.position_left / 100) * FIELD_HEIGHT * AWAY_Y_SCALE;
            q._py = awayCenterY + (py - awayCenterY) * AWAY_OUTFIELD_Y_COMPRESS;
            if (q._py < MIN_PLAYER_Y) q._py = MIN_PLAYER_Y;
        }
    }
    // Rezolva suprapunerile in linii (skip GK la index 0)
    resolveOverlaps(data.away.players.slice(1));
    // Clamp dupa redistribute
    for (var _cj = 1; _cj < data.away.players.length; _cj++) {
        if (data.away.players[_cj]._py < MIN_PLAYER_Y)
            data.away.players[_cj]._py = MIN_PLAYER_Y;
    }
    // Aliniaza linia de jos away cu linia de jos home
    // (shifteaza toti jucatorii away outfield in jos cu diferenta)
    var awayMaxY = 0;
    for (var _am = 1; _am < data.away.players.length; _am++) {
        if (data.away.players[_am]._py > awayMaxY) awayMaxY = data.away.players[_am]._py;
    }
    if (homeMaxY > awayMaxY) {
        var _awayYShift = homeMaxY - awayMaxY;
        for (var _as = 1; _as < data.away.players.length; _as++) {
            data.away.players[_as]._py += _awayYShift;
        }
    }

    // ── Snap X pe linii de formatie away + spacing egal + FWD centrat la GK Y ──────
    (function() {
        var _gkY = data.away.players[0]._py;

        // Grupeaza jucatorii outfield dupa linia de formatie (bucket de 15)
        var _lg = {};
        for (var _j2 = 1; _j2 < data.away.players.length; _j2++) {
            var _bk = Math.round(data.away.players[_j2].position_top / 15) * 15;
            if (!_lg[_bk]) _lg[_bk] = [];
            _lg[_bk].push(_j2);
        }
        // Sorteaza cheile crescator: FWD (position_top mic) → DEF (position_top mare)
        var _lk = [];
        for (var _k in _lg) _lk.push(parseInt(_k));
        _lk.sort(function(a, b) { return a - b; });

        // X egal spatiat intre linii: de la AWAY_X_FROM pana la 75% din range
        var _outRange = 0.75 * (AWAY_X_TO - AWAY_X_FROM);
        var _lxStep  = (_lk.length > 1) ? _outRange / (_lk.length - 1) : _outRange / 2;

        for (var _li = 0; _li < _lk.length; _li++) {
            var _key = _lk[_li];
            var _g   = _lg[_key];
            var _sx  = AWAY_X_FROM + _li * _lxStep;

            // Shift X: FWD → AWAY_FW_MID_X_SHIFT, linia 2 (MID) → AWAY_DMF_X_SHIFT
            var _xs = (_li === 0) ? AWAY_FW_MID_X_SHIFT
                    : (_li === 1 && _lk.length >= 3) ? AWAY_DMF_X_SHIFT
                    : 0;

            for (var _gi = 0; _gi < _g.length; _gi++) {
                data.away.players[_g[_gi]]._px = _sx + _xs;
            }

            // Linia 0 (FWD): centreaza Y la GK Y cu spacing fix de 280px
            if (_li === 0) {
                _g.sort(function(a, b) { return data.away.players[a]._py - data.away.players[b]._py; });
                var _fs = _gkY - ((_g.length - 1) / 2) * 280;
                for (var _fgi = 0; _fgi < _g.length; _fgi++) {
                    data.away.players[_g[_fgi]]._py = _fs + _fgi * 280;
                }
            }
            // DEF / MID: distribuie Y uniform intre min si max deja calculat
            else if (_g.length > 1) {
                _g.sort(function(a, b) { return data.away.players[a]._py - data.away.players[b]._py; });
                var _lo = data.away.players[_g[0]]._py;
                var _hi = data.away.players[_g[_g.length - 1]]._py;
                if (_hi > _lo) {
                    var _st = (_hi - _lo) / (_g.length - 1);
                    for (var _gj = 1; _gj < _g.length - 1; _gj++) {
                        data.away.players[_g[_gj]]._py = _lo + _gj * _st;
                    }
                }
            }
        }
    })();

    for (var j = 0; j < data.away.players.length; j++) {
        var q     = data.away.players[j];
        var n     = pad(j + 1);
        var normX = (q.position_top - X_ATK_TOP) / X_RANGE; // 0=atacant, 1=GK
        var px    = AWAY_X_FROM + normX * (AWAY_X_TO - AWAY_X_FROM);
        if (j === 0) {
            px += AWAY_GK_X_NUDGE;
        } else {
            // Foloseste X pre-calculat din snap-ul liniei de formatie
            if (q._px !== undefined) px = q._px;
            if (px < AWAY_X_MIN) px = AWAY_X_MIN;
        }
        buildPlayer(mainComp, tplComp, "away_player_" + n, q,
            imagesDir + "away_player_" + (j + 1) + ".png",
            px, q._py, playerGlobalIdx);
        playerGlobalIdx++;
    }

    // ── Away Subs — de la centrul canvas-ului spre dreapta ──
    var lastAwaySubGlobalIdx = -1;
    if (awaySubs > 0) {
        var aLeftmost = canvasCenterX + SUB_CENTER_GAP;
        var awaySubStep = SUB_CARD_STEP;
        if (awaySubs > 1) {
            var _aRightmost = aLeftmost + (awaySubs - 1) * awaySubStep;
            if (_aRightmost > SUB_AWAY_RIGHT_LIMIT) {
                awaySubStep = (SUB_AWAY_RIGHT_LIMIT - aLeftmost) / (awaySubs - 1);
            }
        }
        for (var t = 0; t < awaySubs; t++) {
            var sub = data.away.substitutes[t];
            var n   = pad(t + 1);
            var px  = aLeftmost + t * awaySubStep;
            lastAwaySubGlobalIdx = playerGlobalIdx;
            buildPlayer(mainComp, tplComp, "away_sub_" + n, sub,
                imagesDir + "away_sub_" + (t + 1) + ".png",
                px, subY, playerGlobalIdx, dynamicSubScale, true);
            playerGlobalIdx++;
        }
    }

    // ── Markere pe MAIN COMP si pe comp-ul Home-Away ────────────────────
    var markerComps = [mainComp];
    if (matchNameComp) markerComps.push(matchNameComp);

    for (var mc = 0; mc < markerComps.length; mc++) {
        try {
            if (lastHomeSubGlobalIdx >= 0) {
                var mv1 = new MarkerValue("Last Home Sub Stats");
                markerComps[mc].markerProperty.setValueAtTime(lastHomeSubGlobalIdx + 1, mv1);
            }
            if (lastAwaySubGlobalIdx >= 0) {
                var mv2 = new MarkerValue("Last Away Sub Stats");
                markerComps[mc].markerProperty.setValueAtTime(lastAwaySubGlobalIdx + 1, mv2);
                // Seteaza work area end: 28 frame-uri dupa markerul Last Away Sub
                var _fps      = markerComps[mc].frameRate;
                var _markerT  = lastAwaySubGlobalIdx + 1;
                var _waEnd    = _markerT + (28 / _fps);
                markerComps[mc].workAreaStart = 0;
                markerComps[mc].workAreaEnd   = _waEnd;
            }
        } catch(e) {}
    }

    // ── Restaureaza numele template-ului ─────────────────────
    tplComp.name = TEMPLATE_COMP;

    app.endUndoGroup();

    alert("✓ " + match.home_team + "  " + match.home_score +
          " - " + match.away_score + "  " + match.away_team +
          "\n\nHome: " + data.home.players.length + " + " +
          data.home.substitutes.length + " sub" +
          "\nAway: " + data.away.players.length + " + " +
          data.away.substitutes.length + " sub");
})();


// ════════════════════════════════════════════════════════════
//  BUILD PLAYER
// ════════════════════════════════════════════════════════════

function buildPlayer(mainComp, tplComp, id, player, imgPath, px, py, globalIdx, scale, isSubstitute) {

    // 1. Dubleaza comp-ul template
    var pComp  = tplComp.duplicate();
    pComp.name = id;

    // 2. Dubleaza Stats comp si seteaza CTRL
    var statsComp = dupeNested(pComp, STATS_LAYER, "Stats_" + id);
    if (statsComp) {
        fillStats(statsComp, player);

        // Pentru rezerve: FX.change MEREU 1 (indiferent de events)
        if (isSubstitute) {
            var _ctrl = findLayerIn(statsComp, CTRL_LAYER);
            if (_ctrl) fx(_ctrl, FX.change, 1);
        }

        // ── Change / Change Sub logic ──────────────────────────
        // Gaseste exact cele doua layere: "Change.png" si "Change Sub.png"
        var _csLyr = null; // Change Sub.png — pt rezerve
        var _cLyr  = null; // Change.png     — pt titulari
        for (var _li = 1; _li <= statsComp.numLayers; _li++) {
            var _ln = statsComp.layer(_li).name.toLowerCase().replace(/[^a-z0-9]/g, '');
            if (_ln === "changesub" || _ln === "changesubpng") { _csLyr = statsComp.layer(_li); }
            else if (_ln === "change" || _ln === "changepng")  { _cLyr  = statsComp.layer(_li); }
        }
        if (isSubstitute) {
            // Rezerve: Change Sub.png = MEREU vizibil si bifat; Change.png = debifat si ascuns
            if (_csLyr) {
                try { _csLyr.enabled = true; } catch(e) {}
                try { _csLyr.property("Transform").property("Opacity").setValue(100); } catch(e) {}
            }
            if (_cLyr) {
                try { _cLyr.enabled = false; } catch(e) {}
                try { _cLyr.property("Transform").property("Opacity").setValue(0); } catch(e) {}
            }
        } else {
            // Titulari: Change Sub.png = ascuns; Change.png = controlat de efecte (fillStats)
            if (_csLyr) {
                try { _csLyr.enabled = false; } catch(e) {}
                try { _csLyr.property("Transform").property("Opacity").setValue(0); } catch(e) {}
            }
            // Change.png pt titulari e gestionat de fx(ctrl, FX.change, ...) in fillStats
        }

        // 3. Stagger: Stats_home_player_01 porneste la t=1s in pComp,
        //             Stats_home_player_02 la t=2s in pComp etc.
        //    Cautam layer-ul dupa SOURCE (nu dupa nume) pentru ca replaceSource
        //    poate schimba numele layer-ului in AE.
        var statsLyr = null;
        for (var k = 1; k <= pComp.numLayers; k++) {
            var kl = pComp.layer(k);
            if (kl.source && kl.source === statsComp) { statsLyr = kl; break; }
        }
        if (statsLyr) {
            try { statsLyr.startTime = globalIdx; } catch(e) {}
        }

        // Marker pe pComp la t=globalIdx (marcheaza momentul din Main Comp cand apare Stats)
        try {
            var mv = new MarkerValue("Stats");
            pComp.markerProperty.setValueAtTime(globalIdx, mv);
        } catch(e) {}
    }

    // 4. Dubleaza Player Template si seteaza date
    var ptComp = dupeNested(pComp, PT_LAYER, "PT_" + id);
    if (ptComp) {
        fillTemplate(ptComp, player, imgPath, isSubstitute);

        // Fix: extinde outPoint-ul layerului PT la durata intreaga a pComp.
        // Fara asta, la jucatorii cu globalIdx mare, PT se termina inainte ca Stats sa inceapa
        // → numele dispare exact cand apare Stats.
        for (var m = 1; m <= pComp.numLayers; m++) {
            var ml = pComp.layer(m);
            if (ml.source && ml.source === ptComp) {
                try { ml.outPoint = pComp.duration; } catch(e) {}
                break;
            }
        }
    }

    // 5. Adauga in Main Comp si pozitioneaza — toti jucatorii incep la t=0
    var lyr  = mainComp.layers.add(pComp);
    lyr.name = id;
    lyr.property("Position").setValue([px, py]);
    // Seteaza scala daca e specificata (ex. 80 pentru rezerve)
    if (scale !== undefined && scale !== null) {
        try {
            lyr.property("Transform").property("Scale").setValue([scale, scale, 100]);
        } catch(e) {}
    }
}

function dupeNested(parentComp, layerName, newName) {
    for (var i = 1; i <= parentComp.numLayers; i++) {
        var lyr = parentComp.layer(i);
        if (lyr.name === layerName && lyr.source instanceof CompItem) {
            var fresh  = lyr.source.duplicate();
            fresh.name = newName;
            lyr.replaceSource(fresh, false);
            return fresh;
        }
    }
    return null;
}

function fillStats(comp, player) {
    var ctrl = findLayerIn(comp, CTRL_LAYER);
    if (!ctrl) return;

    var ev     = player.events || [];
    var nGoals = cnt(ev, "goal");
    var rating = parseFloat(player.rating) || 0;

    // Debug: scrie in lineup_debug.txt pentru jucatorii cu goluri
    if (nGoals >= 1) {
        try {
            var _dbgDir = (dir || $.global.__LINEUP_SCRIPTS_DIR__ || "").replace(/\\/g,"/").replace(/\/$/,"");
            var _dbgF = new File(_dbgDir + "/lineup_debug.txt");
            _dbgF.encoding = "UTF-8"; _dbgF.open("a");
            _dbgF.writeln("GOALS: " + (player.name||"?") + " | nGoals=" + nGoals +
                          " | events=[" + ev.join(",") + "]");
            _dbgF.close();
        } catch(e) {}
    }

    fx(ctrl, FX.note,          rating);
    fx(ctrl, FX.goal,          has(ev, "goal")            ? 1 : 0);
    fx(ctrl, FX.change,        has(ev, "substituted_out") ? 1 : 0);
    fx(ctrl, FX.yellowCard,    has(ev, "yellow_card")     ? 1 : 0);
    fx(ctrl, FX.redCard,       has(ev, "red_card")        ? 1 : 0);
    fx(ctrl, FX.star,          has(ev, "star") ? 1 : 0);

    // Multiple Goals
    if (nGoals >= 2) {
        // Incearca toate variantele de acces la efect
        var mgOk = false;
        try { ctrl.effect("Multiple Goals").property("Checkbox").setValue(1); mgOk = true; } catch(e) {}
        if (!mgOk) { try { ctrl.effect("Multiple Goals").property(1).setValue(1); mgOk = true; } catch(e) {} }
        if (!mgOk) { fx(ctrl, FX.multipleGoals, 1); }

        var hgOk = false;
        try { ctrl.effect("How Many Goals").property("Slider").setValue(nGoals); hgOk = true; } catch(e) {}
        if (!hgOk) { try { ctrl.effect("How Many Goals").property(1).setValue(nGoals); hgOk = true; } catch(e) {} }
        if (!hgOk) { fx(ctrl, FX.howManyGoals, nGoals); }

        // Scrie in debug ce s-a intamplat
        try {
            var _d2 = (dir || $.global.__LINEUP_SCRIPTS_DIR__ || "").replace(/\\/g,"/").replace(/\/$/,"");
            var _f2 = new File(_d2 + "/lineup_debug.txt");
            _f2.encoding = "UTF-8"; _f2.open("a");
            _f2.writeln("MULTIPLE GOALS: " + (player.name||"?") + " | nGoals=" + nGoals +
                        " | mgOk=" + mgOk + " | hgOk=" + hgOk);
            _f2.close();
        } catch(e) {}
    } else {
        fx(ctrl, FX.multipleGoals, 0);
        fx(ctrl, FX.howManyGoals,  0);
    }
}

function fillTemplate(comp, player, imgPath, isSubstitute) {
    var photoLyr = findLayerIn(comp, PT_PHOTO);
    if (photoLyr) {
        var f = new File(imgPath);
        if (f.exists) {
            try {
                var ftg = app.project.importFile(new ImportOptions(f));
                photoLyr.replaceSource(ftg, false);
            } catch(e) {}
        }
    }
    var numLyr = findLayerIn(comp, PT_NUMBER);
    if (numLyr) setTxtLayer(numLyr, player.number || "");
    var nameLyr = findLayerIn(comp, PT_NAME);
    if (nameLyr) {
        var displayName = abbreviateName(player.name || "", 14);
        setTxtLayer(nameLyr, displayName);
    }
}

// Scurteaza un nume lung la maxim maxLen caractere, pastrand forma naturala:
//   "Arrizabalaga"          (1 token, lung)  → "Arrizabalaga"  (lasat asa)
//   "Gabriel Martinelli"    (2 tokens)        → "G. Martinelli"
//   "Kai Havertz"           (2 tokens, scurt) → "Kai Havertz"   (incape)
//   "Alexander-Arnold"      (1 token cu -)    → "Alexander-Arnold"
function abbreviateName(name, maxLen) {
    if (!name) return "";
    if (name.length <= maxLen) return name;          // incape asa cum e
    var parts = name.split(" ");
    if (parts.length === 1) return name;              // un singur cuvant, nu il taiem
    // Incearca "Prenume Abreviat. + Nume"
    var lastName  = parts[parts.length - 1];
    var firstInit = parts[0].charAt(0).toUpperCase() + ".";
    var candidate = firstInit + " " + lastName;
    if (candidate.length <= maxLen) return candidate;
    // Daca tot prea lung, returneaza doar numele de familie
    if (lastName.length <= maxLen) return lastName;
    // Ultima optiune: trunchiem brutal
    return name.substring(0, maxLen - 1) + ".";
}

// Seteaza sliderele de rating in compozitiile Home Rating / Away Rating
function setRatingSlider(compName, layerName, value) {
    // 1. Gaseste comp-ul — mai intai exact, apoi orice comp al carui nume contine compName
    var comp = findCompByName(compName);
    if (!comp) {
        var cn = compName.toLowerCase();
        for (var _ci = 1; _ci <= app.project.numItems; _ci++) {
            var _it = app.project.item(_ci);
            if (_it instanceof CompItem && _it.name.toLowerCase().indexOf(cn) >= 0) {
                comp = _it; break;
            }
        }
    }
    if (!comp) {
        // Afiseaza toate comp-urile disponibile ca sa stim cum se numesc
        var allComps = [];
        for (var _di = 1; _di <= app.project.numItems; _di++) {
            if (app.project.item(_di) instanceof CompItem)
                allComps.push(app.project.item(_di).name);
        }
        alert("RATING COMP NOT FOUND: '" + compName + "'\n\n" +
              "Available comps in project:\n" + allComps.join("\n") +
              "\n\nUpdate HOME_RATING_COMP / AWAY_RATING_COMP in populate_lineup.jsx");
        return;
    }

    // 2. Gaseste layer-ul — exact, apoi fuzzy, apoi primul layer cu efect Slider
    var lyr = findLayerIn(comp, layerName);
    if (!lyr) {
        // fuzzy: cauta orice layer al carui nume contine "rating" (case insensitive)
        for (var _li = 1; _li <= comp.numLayers; _li++) {
            if (comp.layer(_li).name.toLowerCase().indexOf("rating") >= 0) {
                lyr = comp.layer(_li); break;
            }
        }
    }
    if (!lyr) {
        // fallback: primul layer care are macar un efect
        for (var _li2 = 1; _li2 <= comp.numLayers; _li2++) {
            try {
                if (comp.layer(_li2).effect(1)) { lyr = comp.layer(_li2); break; }
            } catch(e) {}
        }
    }
    if (!lyr) {
        // Afiseaza layerele disponibile in comp ca sa stim cum se numesc
        var allLyrs = [];
        for (var _lx = 1; _lx <= comp.numLayers; _lx++)
            allLyrs.push(comp.layer(_lx).name);
        alert("RATING LAYER NOT FOUND in comp '" + comp.name + "'\n" +
              "Looking for: '" + layerName + "'\n\n" +
              "Available layers:\n" + allLyrs.join("\n") +
              "\n\nUpdate HOME_RATING_LAYER / AWAY_RATING_LAYER in populate_lineup.jsx");
        return;
    }

    // 3. Seteaza slider-ul — 4 variante pentru compatibilitate cu toate versiunile AE
    var set = false;
    if (!set) try { lyr.effect("Slider Control").property("Slider").setValue(value); set = true; } catch(e) {}
    if (!set) try { lyr.effect("Slider Control").property(1).setValue(value); set = true; } catch(e) {}
    if (!set) try { lyr.effect(1).property(1).setValue(value); set = true; } catch(e) {}
    if (!set) try {
        var fxp = lyr.property("ADBE Effect Parade");
        if (fxp && fxp.numProperties > 0) { fxp.property(1).property(1).setValue(value); set = true; }
    } catch(e) {}
    if (!set) {
        // Debug: afiseaza detalii complete despre comp/layer/efecte
        var dbg = "Slider negasit in: " + compName + " / layer: " + lyr.name + " (val=" + value + ")\n";
        dbg += "Efecte pe layer:\n";
        try {
            for (var _ef = 1; _ef <= lyr.numProperties; _ef++) {
                try { dbg += "  [" + _ef + "] " + lyr.property(_ef).name + "\n"; } catch(e) {}
            }
        } catch(e) {}
        alert(dbg);
    }
}

// adjustMatchCompKeyframes — ELIMINAT intentionat.
// Keyframe-urile din Home-Away comp NU sunt modificate de script.

// Inlocuieste sursa unui layer imagine din comp cu un fisier PNG de pe disk
function replaceImgLayer(comp, layerName, filePath) {
    var lyr = findLayerIn(comp, layerName);
    if (!lyr) return;
    var f = new File(filePath);
    if (!f.exists) return;
    try {
        var ftg = app.project.importFile(new ImportOptions(f));
        lyr.replaceSource(ftg, false);
    } catch(e) {}
}

function clearOldLayers(comp) {
    var del = [];
    for (var i = 1; i <= comp.numLayers; i++) {
        if (/^(home|away)_(player|sub)_\d+$/.test(comp.layer(i).name))
            del.push(comp.layer(i));
    }
    for (var j = 0; j < del.length; j++) del[j].remove();
}


// ════════════════════════════════════════════════════════════
//  HELPERS
// ════════════════════════════════════════════════════════════

function findCompByName(n) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === n) return it;
    }
    return null;
}
function findLayerIn(comp, n) {
    for (var i = 1; i <= comp.numLayers; i++)
        if (comp.layer(i).name === n) return comp.layer(i);
    return null;
}
// Cauta layer ignorand majuscule, spatii, punctuatie si extensia fisierului
// Ex: findLayerFuzzy(comp, "changesub") gaseste "Change Sub.png", "change-sub.png" etc.
function findLayerFuzzy(comp, keyword) {
    var kw = keyword.toLowerCase().replace(/[^a-z0-9]/g, '');
    for (var i = 1; i <= comp.numLayers; i++) {
        var norm = comp.layer(i).name.toLowerCase().replace(/[^a-z0-9]/g, '');
        if (norm === kw || norm.indexOf(kw) === 0 || kw.indexOf(norm) === 0) {
            return comp.layer(i);
        }
    }
    return null;
}
function fx(layer, name, val) {
    // Proba 1: exact prin shortcut .effect(name)
    try { layer.effect(name).property(1).setValue(val); return; } catch(e) {}
    // Proba 2: iterare prin layer.property("Effects") — mai fiabil in toate versiunile AE
    var nk = name.toLowerCase().replace(/[^a-z0-9]/g, '');
    try {
        var efGroup = layer.property("Effects");
        var nProps  = efGroup.numProperties;
        for (var _fxi = 1; _fxi <= nProps; _fxi++) {
            try {
                var _ef = efGroup.property(_fxi);
                if (_ef.name.toLowerCase().replace(/[^a-z0-9]/g, '') === nk) {
                    _ef.property(1).setValue(val);
                    return;
                }
            } catch(e2) {}
        }
    } catch(e3) {}
}
function setTxt(comp, layerName, val) {
    var l = findLayerIn(comp, layerName);
    if (l) setTxtLayer(l, val);
}
function setTxtLayer(layer, val) {
    try {
        var prop = layer.property("Source Text");
        if (prop.expressionEnabled) prop.expressionEnabled = false;
        // Nu crea keyframe-uri: daca layerul e animat, sarim peste
        if (prop.numKeys && prop.numKeys > 0) return;
        var td = prop.value;
        td.text = String(val);
        try { prop.setValue(td); } catch(e1) {}
    } catch(e) {}
}
function pad(n) { return n < 10 ? "0" + n : "" + n; }

// Calculeaza pasul minim necesar pentru un jucator in functie de lungimea numelui afisat
function nameMinStep(name) {
    var abbrev = abbreviateName(name || "", 14);
    var w      = Math.max(CARD_W_VISUAL, abbrev.length * PX_PER_CHAR);
    return w + CARD_GAP;
}

// Rezolva suprapunerile in cadrul aceleiasi linii (aceeasi position_top).
// Spacing-ul dintre jucatori este calculat in functie de lungimea numelui lor afisat.
function resolveOverlaps(players) {
    // Grupeaza indicii dupa position_top (aceeasi linie de formatatie)
    var groups = {};
    for (var i = 0; i < players.length; i++) {
        var k = Math.round(players[i].position_top);
        if (!groups[k]) groups[k] = [];
        groups[k].push(i);
    }
    for (var k in groups) {
        var g = groups[k];
        if (g.length <= 1) continue;

        // Sorteaza jucatorii din grup dupa _py curent (sus-jos pe ecran)
        g.sort(function(a, b) { return players[a]._py - players[b]._py; });

        // Calculeaza pasul minim intre perechile adiacente (bazat pe lungimea numelui)
        var steps = [];
        for (var j = 1; j < g.length; j++) {
            var s1 = nameMinStep(players[g[j-1]].name);
            var s2 = nameMinStep(players[g[j]].name);
            steps.push(Math.max(s1, s2));
        }

        // Verifica daca exista suprapuneri
        var overlap = false;
        for (var j = 1; j < g.length; j++) {
            if (players[g[j]]._py - players[g[j-1]]._py < steps[j-1]) {
                overlap = true; break;
            }
        }
        if (!overlap) continue;

        // Distribuie centrat pe centrul actual al grupului, cu pasi variabili per nume
        var totalSpan = 0;
        for (var j = 0; j < steps.length; j++) totalSpan += steps[j];
        var cen = 0;
        for (var j = 0; j < g.length; j++) cen += players[g[j]]._py;
        cen /= g.length;
        var start = cen - totalSpan / 2;
        players[g[0]]._py = start;
        for (var j = 1; j < g.length; j++) {
            players[g[j]]._py = players[g[j-1]]._py + steps[j-1];
        }
    }
}
// Distribuie uniform Y-ul jucatorilor in cadrul aceleiasi coloane de formatie.
// Grupare: position_top rotunjit la multiplu de 15 (prinde WB + CM in acelasi bucket).
// Ancorele min/max raman fixe; jucatorii interiori sunt redistribuiti egal intre ele.
function evenlySpaceColumns(players) {
    var groups = {};
    for (var i = 0; i < players.length; i++) {
        var k = Math.round(players[i].position_top / 15) * 15;
        if (!groups[k]) groups[k] = [];
        groups[k].push(i);
    }
    for (var k in groups) {
        var g = groups[k];
        if (g.length <= 1) continue;
        g.sort(function(a, b) { return players[a]._py - players[b]._py; });
        var lo = players[g[0]]._py;
        var hi = players[g[g.length - 1]]._py;
        if (hi <= lo) continue;
        var step = (hi - lo) / (g.length - 1);
        for (var j = 1; j < g.length - 1; j++) {
            players[g[j]]._py = lo + j * step;
        }
    }
}

function has(arr, v) {
    for (var i = 0; i < arr.length; i++) if (arr[i] === v) return true;
    return false;
}
function cnt(arr, v) {
    var c = 0;
    for (var i = 0; i < arr.length; i++) if (arr[i] === v) c++;
    return c;
}
