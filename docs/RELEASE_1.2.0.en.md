# RecurGO v1.2.0 Release Notes

This release adds **independent analysis report export**. After analyzing a game, export the results as a single HTML file. The report includes an interactive viewer and opens in a browser, such as Edge or Chrome.

This release offers **TF3** and **B28** editions with the same application features, including report export. The TF3 edition uses KataGo 1.18.2 with the TF3 model; the B28 edition uses KataGo 1.16.5 with the B28 model. Choose one installer. Installing the other edition in the same location switches editions while retaining games, settings, and saved analysis; results from different models remain separate.

Reports include:

- **Move-by-move review**: navigate the board using previous/next controls, move numbers, a slider, and existing game variations.
- **Candidates and reference variations**: inspect candidate moves, win rates, score leads, and visits, then replay saved candidate variations step by step.
- **Full-game statistics**: explore win-rate trends, move quality, problem moves, match rates, and an overview, with whole-game, opening, middle-game, and endgame scopes.
- **Linked charts**: click a win-rate point or problem move to jump to its position.

Reports support Chinese and English, desktop and mobile layouts, and offline viewing.

If the board or buttons do not respond, please open the report in a browser, such as Edge or Chrome. If the report still does not respond after opening it in a browser, check whether JavaScript is enabled.

A report contains the analysis saved at export time. Missing or incomplete positions are labeled explicitly. Complete **Analyze full game** before exporting if you need a complete report.

Project:
https://github.com/Izaak217/RecurGO
