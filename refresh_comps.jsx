// ── JSON polyfill for ExtendScript (AE on macOS has no native JSON) ──
if (typeof JSON === "undefined") { JSON = {}; }
if (typeof JSON.parse !== "function") {
    JSON.parse = function (text) { return eval("(" + String(text) + ")"); };
}
if (typeof JSON.stringify !== "function") {
    JSON.stringify = function (o) {
        var t = typeof o;
        if (o === null || t === "undefined") return "null";
        if (t === "number" || t === "boolean") return String(o);
        if (t === "string") return '"' + o.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t") + '"';
        if (o instanceof Array) {
            var a = [];
            for (var i = 0; i < o.length; i++) a.push(JSON.stringify(o[i]));
            return "[" + a.join(",") + "]";
        }
        if (t === "object") {
            var b = [];
            for (var k in o) if (o.hasOwnProperty(k)) b.push(JSON.stringify(k) + ":" + JSON.stringify(o[k]));
            return "{" + b.join(",") + "}";
        }
        return "null";
    };
}

/**
 * refresh_comps.jsx — Update AE compositions with latest stats from data.json
 * ============================================================================
 * Run this after refresh_stats.py has updated data.json.
 * Updates ratings, events (goals, cards, etc.) and score — without touching
 * player positions, photos or any other layout.
 *
 * Called automatically by "Refresh Stats" in the Lineup Panel extension.
 */

(function () {

    // ── Config — must match populate_lineup.jsx ───────────────────
    var MAIN_COMP_NAME    = "MAIN COMP";
    var LAYER_SCORE       = "Score";
    var LAYER_HOME_TEAM   = "Home Team";
    var LAYER_AWAY_TEAM   = "Away Team";
    var HOME_RATING_COMP  = "Home Rating";
    var AWAY_RATING_COMP  = "Away Rating";
    var HOME_RATING_LAYER = "Home - Rating";
    var AWAY_RATING_LAYER = "Away - Rating";
    var CTRL_LAYER        = "CTRL";

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
    // ─────────────────────────────────────────────────────────────

    var dir = (typeof $.global.__LINEUP_SCRIPTS_DIR__ !== "undefined")
        ? String($.global.__LINEUP_SCRIPTS_DIR__).replace(/\\/g, "/").replace(/\/$/, "")
        : (new File($.fileName)).parent.fsName.replace(/\\/g, "/").replace(/\/$/, "");

    var dataPath = dir + "/flashscore_output/data.json";
    var jf = new File(dataPath);
    if (!jf.exists) {
        alert("data.json not found:\n" + dataPath + "\n\nRun the scraper first.");
        return;
    }
    jf.encoding = "UTF-8";
    jf.open("r");
    var data = JSON.parse(jf.read());
    jf.close();

    var match = data.match;

    // ── Find MAIN COMP ───────────────────────────────────────────
    var mainComp = null;
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === MAIN_COMP_NAME) {
            mainComp = it; break;
        }
    }
    if (!mainComp) mainComp = app.project.activeItem;
    if (!mainComp || !(mainComp instanceof CompItem)) {
        alert("Please select MAIN COMP and try again.");
        return;
    }

    app.beginUndoGroup("Refresh Stats");

    var updated = 0;
    var skipped = 0;

    // ── 1. Update score ──────────────────────────────────────────
    var scoreStr = match.home_score + "-" + match.away_score;
    var scoreLyr = findLayerIn(mainComp, LAYER_SCORE);
    if (scoreLyr) {
        setTxtLayer(scoreLyr, scoreStr);
        updated++;
    }

    // ── 2. Update team names ──────────────────────────────────────
    setTxt(mainComp, LAYER_HOME_TEAM, match.home_team);
    setTxt(mainComp, LAYER_AWAY_TEAM, match.away_team);

    // ── 3. Update average rating sliders ─────────────────────────
    if (match.home_avg_rating)
        setRatingSlider(HOME_RATING_COMP, HOME_RATING_LAYER, parseFloat(match.home_avg_rating));
    if (match.away_avg_rating)
        setRatingSlider(AWAY_RATING_COMP, AWAY_RATING_LAYER, parseFloat(match.away_avg_rating));

    // ── 4. Update player stats + kit numbers ──────────────────────
    var groups = [
        { list: data.home.players,      prefix: "home_player_", isSub: false },
        { list: data.home.substitutes,  prefix: "home_sub_",    isSub: true  },
        { list: data.away.players,      prefix: "away_player_", isSub: false },
        { list: data.away.substitutes,  prefix: "away_sub_",    isSub: true  }
    ];

    var unchanged = 0;
    var kitsUpdated = 0;

    for (var g = 0; g < groups.length; g++) {
        var grp = groups[g];
        for (var p = 0; p < grp.list.length; p++) {
            var player = grp.list[p];
            var idx    = p + 1;
            // Suporta atat "home_player_1" cat si "home_player_01" (zero-padded din populate_lineup)
            var id       = grp.prefix + idx;
            var idPad    = grp.prefix + (idx < 10 ? "0" + idx : idx);

            var statsComp = findCompByName("Stats_" + id)
                         || findCompByName("Stats_" + idPad);
            if (!statsComp) { skipped++; continue; }

            var ctrl = findLayerIn(statsComp, CTRL_LAYER);
            if (!ctrl) { skipped++; continue; }

            if (!playerNeedsUpdate(ctrl, player, grp.isSub)) {
                unchanged++;
            } else {
                refreshPlayerStats(ctrl, player, grp.isSub);
                updated++;
            }

            // ── Kit number: actualizeaza intotdeauna layer-ul "1" din PT comp ────
            if (player.number !== undefined && player.number !== null) {
                var ptComp = findCompByName("PT_" + id)
                          || findCompByName("PT_" + idPad);
                if (ptComp) {
                    var numLyr = findLayerIn(ptComp, "1");
                    if (numLyr) {
                        setTxtLayer(numLyr, String(player.number || ""));
                        kitsUpdated++;
                    }
                }
            }
        }
    }

    app.endUndoGroup();

    var msg = "\u2713 Refresh complete!\n\n";
    msg += "\u2022 Score: " + scoreStr + "\n";
    msg += "\u2022 Avg: " + (match.home_avg_rating || "?") + " / " + (match.away_avg_rating || "?") + "\n";
    msg += "\u2022 Stats updated: " + updated + "\n";
    if (kitsUpdated > 0)
        msg += "\u2022 Kit numbers synced: " + kitsUpdated + "\n";
    if (unchanged > 0)
        msg += "\u2022 Unchanged (skipped): " + unchanged + "\n";
    if (skipped > 0)
        msg += "\u2022 Comp not found: " + skipped + "\n";
    msg += "\nNo re-populate needed \u2014 positions unchanged.";
    alert(msg);

    // ── Helpers ───────────────────────────────────────────────────

    /**
     * Compara valorile curente din AE cu cele din data.json.
     * Returneaza true daca cel putin o valoare s-a schimbat.
     */
    function playerNeedsUpdate(ctrl, player, isSub) {
        try {
            var ev      = player.events || [];
            var rating  = parseFloat(player.rating) || 0;
            var nGoals  = cnt(ev, "goal");
            var expGoal   = has(ev, "goal")         ? 1 : 0;
            var expYellow = has(ev, "yellow_card")   ? 1 : 0;
            var expRed    = has(ev, "red_card")      ? 1 : 0;
            var expStar   = has(ev, "star")          ? 1 : 0;
            var expChange = isSub ? 1 : (has(ev, "substituted_out") ? 1 : 0);
            var expMG     = nGoals >= 2 ? 1 : 0;

            var curNote = 0;
            try { curNote = ctrl.effect(FX.note).property(1).value; } catch(e) { return true; }
            if (Math.abs(curNote - rating) > 0.005) return true;

            var curGoal = 0;
            try { curGoal = ctrl.effect(FX.goal).property(1).value; } catch(e) { return true; }
            if (curGoal !== expGoal) return true;

            var curYellow = 0;
            try { curYellow = ctrl.effect(FX.yellowCard).property(1).value; } catch(e) { return true; }
            if (curYellow !== expYellow) return true;

            var curRed = 0;
            try { curRed = ctrl.effect(FX.redCard).property(1).value; } catch(e) { return true; }
            if (curRed !== expRed) return true;

            var curStar = 0;
            try { curStar = ctrl.effect(FX.star).property(1).value; } catch(e) { return true; }
            if (curStar !== expStar) return true;

            var curChange = 0;
            try { curChange = ctrl.effect(FX.change).property(1).value; } catch(e) { return true; }
            if (curChange !== expChange) return true;

            var curMG = 0;
            try {
                try { curMG = ctrl.effect("Multiple Goals").property("Checkbox").value; }
                catch(e) { curMG = ctrl.effect("Multiple Goals").property(1).value; }
            } catch(e) { return true; }
            if (curMG !== expMG) return true;

            return false;
        } catch(e) {
            return true; // la orice eroare de citire → actualizeaza safe
        }
    }

    /**
     * Scrie efectele pe ctrl layer. ctrl este primit direct (deja gasit).
     */
    function refreshPlayerStats(ctrl, player, isSub) {
        var ev     = player.events || [];
        var rating = parseFloat(player.rating) || 0;
        var nGoals = cnt(ev, "goal");

        fx(ctrl, FX.note,       rating);
        fx(ctrl, FX.goal,       has(ev, "goal")            ? 1 : 0);
        fx(ctrl, FX.yellowCard, has(ev, "yellow_card")     ? 1 : 0);
        fx(ctrl, FX.redCard,    has(ev, "red_card")        ? 1 : 0);
        fx(ctrl, FX.star,       has(ev, "star")            ? 1 : 0);

        if (isSub) {
            fx(ctrl, FX.change, 1);  // subs always show change icon
        } else {
            fx(ctrl, FX.change, has(ev, "substituted_out") ? 1 : 0);
        }

        if (nGoals >= 2) {
            var mgOk = false;
            try { ctrl.effect("Multiple Goals").property("Checkbox").setValue(1); mgOk = true; } catch(e) {}
            if (!mgOk) { try { ctrl.effect("Multiple Goals").property(1).setValue(1); } catch(e) {} }

            var hgOk = false;
            try { ctrl.effect("How Many Goals").property("Slider").setValue(nGoals); hgOk = true; } catch(e) {}
            if (!hgOk) { try { ctrl.effect("How Many Goals").property(1).setValue(nGoals); } catch(e) {} }
        } else {
            fx(ctrl, FX.multipleGoals, 0);
            fx(ctrl, FX.howManyGoals,  0);
        }
    }

    function setRatingSlider(compName, layerName, value) {
        var comp = findCompByName(compName);
        if (!comp) return;

        var lyr = findLayerIn(comp, layerName);
        if (!lyr) {
            // fallback: first layer with "rating" in name
            for (var i = 1; i <= comp.numLayers; i++) {
                if (comp.layer(i).name.toLowerCase().indexOf("rating") >= 0) {
                    lyr = comp.layer(i); break;
                }
            }
        }
        if (!lyr) return;

        var set = false;
        if (!set) try { lyr.effect("Slider Control").property("Slider").setValue(value); set = true; } catch(e) {}
        if (!set) try { lyr.effect("Slider Control").property(1).setValue(value); set = true; } catch(e) {}
        if (!set) try { lyr.effect(1).property(1).setValue(value); } catch(e) {}
    }

    function findCompByName(n) {
        for (var i = 1; i <= app.project.numItems; i++) {
            var it = app.project.item(i);
            if (it instanceof CompItem && it.name === n) return it;
        }
        return null;
    }

    function findLayerIn(comp, n) {
        for (var i = 1; i <= comp.numLayers; i++) {
            if (comp.layer(i).name === n) return comp.layer(i);
        }
        return null;
    }

    function fx(layer, name, val) {
        try { layer.effect(name).property(1).setValue(val); return; } catch(e) {}
        var nk = name.toLowerCase().replace(/[^a-z0-9]/g, "");
        try {
            var efGroup = layer.property("Effects");
            for (var i = 1; i <= efGroup.numProperties; i++) {
                try {
                    var ef = efGroup.property(i);
                    if (ef.name.toLowerCase().replace(/[^a-z0-9]/g, "") === nk) {
                        ef.property(1).setValue(val); return;
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
            if (prop.numKeys && prop.numKeys > 0) return;
            var td = prop.value;
            td.text = String(val);
            try { prop.setValue(td); } catch(e1) {}
        } catch(e) {}
    }

    function has(arr, val) {
        for (var i = 0; i < arr.length; i++) if (arr[i] === val) return true;
        return false;
    }

    function cnt(arr, val) {
        var n = 0;
        for (var i = 0; i < arr.length; i++) if (arr[i] === val) n++;
        return n;
    }

})();
