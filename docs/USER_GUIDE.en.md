# RecurGO User Manual (v1.0.1)

English | [简体中文](USER_GUIDE.md)

This manual explains everyday use of RecurGO. For installation, downloads, CUDA/cuDNN, and environment checks, see the [Windows Installation Guide](INSTALL_WINDOWS.en.md). Developers running from source should use [Run from source](SOURCE_SETUP.en.md).

## Three common tasks

- **Record or study a position:** New game → Manual study → play on the board → enable real-time analysis when needed.
- **Play the AI:** New game → Fair play or Assisted play → choose a color and difficulty → play.
- **Review a game:** Game library or Import SGF → open the game → Analyze full game → inspect the charts on the right.

## Start the application and find controls

Start RecurGO from the Start Menu or the optional desktop shortcut. Before first use, follow the [installation guide](INSTALL_WINDOWS.en.md) to pass the separate KataGo analysis environment check. Run it again after changing the GPU driver, CUDA/cuDNN paths, or models.

If KataGo is unavailable, the board and game library may still open, but AI play, candidate
moves, and full-game analysis will not work. Use the checker's actual analysis result to judge
whether the engine is ready.

| Location | Purpose |
| --- | --- |
| Top toolbar | New game, library, undo, pass, analysis, import/export, mode, difficulty, play-as color, and analysis switches. |
| White-backed button at the toolbar's right edge | Opens toolbar items that do not fit when the window is narrow. |
| Menu / 菜单 at the top left | A fallback for game, play, analysis, and settings controls; it shares the toolbar's state. |
| Board and navigation below it | Play moves; during review, jump with First, Previous, the slider, move number, Next, or Last. |
| Left panel | Rules-based explanation of the selected candidate; optional supplemental Ollama text. |
| Right panel | KataGo status, candidate moves, and full-game review charts. |

## Start and play a game

1. Select **New game / 新棋局**. Enter a game name; Black and White player names are optional.
2. Choose a mode and confirm. **Manual study / 手动打谱** lets users record both sides' moves.
   **Fair play / 公平对战** plays against the local AI with real-time analysis and ownership
   disabled. **Assisted play / 辅助对战** plays against the AI and permits optional analysis.
3. In a play mode, choose Black or White and a difficulty. The AI plays first when users choose
   White. Beginner through Expert use different Human SL human-style levels; **Strongest / 最强**
   uses the main model's best searched move.
4. Click a legal board intersection. Wait for the AI when it is its turn. Every move is saved
   automatically in the local game library.

Users can also change the current game's mode, difficulty, or play-as color from the toolbar.
These controls are temporarily disabled during full-game analysis. **Undo** and **Redo** move
through the game; in play modes they also handle the corresponding AI move. **Pass** skips a
turn. Two consecutive passes open scoring; users can also select **Finish / Score**.

Scoring previews the current estimate, then completes a fresh KataGo analysis with the
configured visits. Version 1.0.1 also considers connected groups, eyes and search
variation. Users review and correct the suggestion before confirming; automatic judgments
can still be wrong.

1. Click intersections to cycle through **Black, White, shared equally, unresolved**, or select
   a fixed brush. Split squares mean shared empty points, half a stone for each side; orange
   question marks need review. AI uncertainty is not evidence of seki.
2. In seki, private eyes belong to their owner; only common empty points are split. Use
   **Toggle dead group** to remove a whole group, then assign the vacated intersections.
   Click again to restore the group. A whole group assigned to its opponent is also shown dead.
3. **Analyze score again** preserves users’ corrections. Undo all corrections restores the
   latest suggestion. Manual Black, White and shared assignments take priority; group-status
   disagreements are advisory and do not block confirmation. Without AI, users can assign
   every point manually. Any unresolved points must still be completed.
4. Ordinary unresolved ko is not automatically shared. Under Chinese rule 21, contestable
   points left after an agreed end are treated as seki. Disputed life and death is resolved by
   further play, starting with the side claiming the stones are dead. Merely discovering a new
   tactic after an agreed end does not reopen play. Special cyclic-ko rulings are not automated.

Live stones and owned empty points are counted once; komi is applied once. Shared points can
produce half-stone area totals, and 3¾-stone compensation can produce quarter-stone margins.
Confirm the reviewed map, then close the result window to save it. Reopening shows the saved
map and dead groups; later SGF exports retain the result. Earlier games are not rescored.
See the [Chinese Weiqi Association rules](https://wqwh.weiqi.org.cn/rules/).
**Resign** asks for confirmation. Creating a new game does not delete the previous one.

## Analyze the current position

After configuring KataGo, enable **Real-time analysis / 实时分析**. The candidate table on the
right shows move, human preference, win rate, score lead, and visits. Select a candidate for
an explanation in the left panel. Values can change while the search runs. **Ownership / 领地**
shows an area estimate on the board. Both switches are unavailable during fair play.

**Analysis settings / 分析设置** changes visits per position for real-time analysis, scoring and
full-game review. The initial value is 800. More visits usually take longer; fewer visits can
leave the search incomplete. This setting does not change Strongest play's search settings,
and old cached analysis is not presented as if it used the new value. No fixed visits number
is a universal Strongest standard for every position and computer.

## Open games and review the whole game

Select **Game library / 棋谱库** to search by name, player, date, result, or mode. Select a
game and choose **Open game / 进入棋谱**, or double-click it. For an unfinished AI game, choose
**Continue playing / 继续对弈** or **Review only / 仅复盘**. You can edit its name and player
details in the library. Deleting a game permanently removes its branches and related review
data and cannot be undone.

Use the controls below the board to step through a saved or imported game. Select
**Analyze full game / 全盘AI分析** to begin; the same button can stop the run. Completed positions
are saved, and another run can continue unfinished positions. The review area has Win-rate
trend, Move quality, Problem moves, Match rate, and Overview views. **Scope / 范围** selects the
whole game, opening, middle game, or endgame. Click problem-move or match-rate marks to jump
to their positions. Review grades are analysis-based estimates, not infallible judgments.

## Import, recognize, and export

- **Import SGF / 导入 SGF** saves an imported game with its variations and comments, then
  opens it for review.
- **Recognize image / 图片识谱** uses an image from the clipboard or a local file. If needed,
  choose board size, rotate or mirror, select four grid corners, and correct individual stones.
  Then choose Black or White to play. This creates a static position; it cannot reconstruct
  move order, captures, or ko history that the picture does not show.
- **Export SGF / 导出 SGF** saves the current game as `.sgf`. It may contain player names,
  comments, and the result, so inspect it before sharing.

Image recognition runs locally; the image is not uploaded.

## Language, appearance, and optional local AI text

Open **Preferences / 偏好设置 → Language / 语言**, select English or 简体中文, and choose OK.
The interface switches immediately. English is the default on a fresh setup. User-entered
game and player names keep their original text. The same dialog offers board, stone, sound,
and volume settings; **Mute / 静音** on the toolbar switches sound quickly.

The built-in rules explanation does not require Ollama. Optional Ollama adds local text only;
it does not determine KataGo moves or figures. Follow the
[Windows installation guide](INSTALL_WINDOWS.en.md), then enable and select it under **Local AI explanation
settings / 本机 AI 解释设置**. Model text can be wrong, and choosing a language does not
guarantee every response will follow it. Use KataGo for moves and numerical estimates.

## Local data, backups, and uninstalling

The installed application stores games, settings, analysis caches, and logs under
`%LOCALAPPDATA%\RecurGO` by default. `RECURGO_DATA_DIR` can select another data directory.
Before reporting a problem, remove private games, names, database contents, local paths in
logs, and other personal information. Report security issues privately under the
[security policy](../SECURITY.en.md).

Close RecurGO before copying the data directory for a complete backup. It may contain private
games, names, analysis caches, environment paths, and optional downloaded Ollama models. To
share one game, use **Export SGF** and inspect the exported file. Uninstalling the application
does not automatically remove its separate user data directory; reinstalling or updating the
application does not overwrite that directory as program files.

## Common problems

| Symptom | First check |
| --- | --- |
| No candidate moves | Check that real-time analysis is enabled and fair play is off. Then run the separate checker and read KataGo status. |
| AI does not play | Is it the AI's turn, and did the separate checker complete a real analysis? AI play needs a working engine. |
| Controls disappear in a narrow window | Open the white-backed overflow button at the toolbar's right edge, or use Menu / 菜单. |
| Image recognition is inaccurate | Select the correct board size and four corners, then correct the position manually. |
| No Ollama text | Check the local service, model, and explanation settings. KataGo analysis works independently. |

For download and configuration details, use the [Windows installation guide](INSTALL_WINDOWS.en.md).
