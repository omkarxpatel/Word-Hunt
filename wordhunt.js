import { initLetterTree, isWord } from "./lettertree.js";
// TCNEOBRURESDWTDS
let root = initLetterTree();
let board = [
    ["", "", "", ""],
    ["", "", "", ""],
    ["", "", "", ""],
    ["", "", "", ""],
];

// let board = [
//   ["t", "e", "s", "t"],
//   ["s", "o", "l", "o"],
//   ["s", "d", "m", "e"],
//   ["n", "a", "s", "b"],
// ];

let points = [
    0, 0, 0, 100, 400, 800, 1400, 1800, 2200, 2600, 3000, 3400, 3800, 4200, 4600,
    5000,
];


const drawLine = (x1, y1, x2, y2) => {
    let length = Math.sqrt(Math.pow(x1 - x2, 2) + Math.pow(y1 - y2, 2));
    let line = document.createElement("div");

    let xMid = (x1 + x2) / 2;
    let yMid = (y1 + y2) / 2;

    let slopeInRad = Math.atan2(y1 - y2, x1 - x2);
    let slopeInDeg = (slopeInRad * 180) / Math.PI;

    line.className = "line";
    line.style.width = `${length}px`;
    line.style.top = `${yMid - 3}px`;
    line.style.left = `${xMid - length / 2}px`;
    line.style.transform = `rotate(${slopeInDeg}deg)`;

    return line;
};

const getAdjacentNodes = (currentY, currentX) => {
    let adjNodes = [];
    for (let y = -1; y < 2; y++) {
        for (let x = -1; x < 2; x++) {
            if (x === 0 && y === 0) {
                continue;
            }
            let newY = currentY + y;
            let newX = currentX + x;
            if (newY >= 0 && newY < 4 && newX >= 0 && newX < 4) {
                adjNodes.push([newY, newX]);
            }
        }
    }
    return adjNodes;
};

const solver = () => {
    let wordsFound = [];

    for (let y = 0; y < 4; y++) {
        for (let x = 0; x < 4; x++) {
            if (
                boardState.getAttribute("state").toUpperCase() == "TCNEOBRURESDWTDS" &&
                y == 0 &&
                x == 3
            ) {
                console.log("here");
            }
            let visitedNodes = [
                [false, false, false, false],
                [false, false, false, false],
                [false, false, false, false],
                [false, false, false, false],
            ];
            visitedNodes[y][x] = true;

            const recursiveSearch = (y, x, node, partialWord, visited, p) => {
                if (node.isWord) {
                    let del = false;
                    for (let i of wordsFound) {
                        if (i.word == partialWord) {
                            del = true;
                        }
                    }
                    if (!del) {
                        wordsFound.push({
                            word: partialWord,
                            points: points[partialWord.length],
                            path: JSON.stringify(p),
                        });
                    }
                }

                for (let adjNode of getAdjacentNodes(y, x)) {
                    if (visited[adjNode[0]][adjNode[1]]) {
                        continue;
                    }
                    let char = board[adjNode[0]][adjNode[1]];
                    if (node.children.has(char)) {
                        visited[adjNode[0]][adjNode[1]] = true;
                        p.push([adjNode[0], adjNode[1]]);
                        recursiveSearch(
                            adjNode[0],
                            adjNode[1],
                            node.children.get(char),
                            partialWord + char,
                            visited,
                            p
                        );
                        visited[adjNode[0]][adjNode[1]] = false;
                        p.splice(-1);
                    }
                }
            };
            if (board[y][x] != "") {
                recursiveSearch(
                    y,
                    x,
                    root.children.get(board[y][x]),
                    board[y][x],
                    visitedNodes,
                    [[y, x]]
                );
            } else {
                recursiveSearch(y, x, root, "", visitedNodes, []);
            }
        }
    }
    return wordsFound;
};

const updateBoard = (board) => {
    for (let i = 0; i < 16; i++) {
        let tile = board.children[i];
        if (i < board.getAttribute("state").length) {
            tile.innerHTML = board.getAttribute("state")[i];
        } else {
            tile.innerHTML = "";
        }
    }
};

const createBoard = (state) => {
    let board = document.createElement("div");
    board.className = "board_state";
    board.setAttribute("state", state);
    for (let i = 0; i < 16; i++) {
        let tile = document.createElement("div");
        tile.className = "tile";
        tile.id = i;
        board.appendChild(tile);
    }
    updateBoard(board);
    return board;
};

const drawLines = (board, wordObj) => {
    let rect = board.getBoundingClientRect();
    let x1 = rect.left + wordObj["path"][0][1] * 50 + 25;
    let y1 = rect.top + wordObj["path"][0][0] * 50 + 25;

    let start = document.createElement("div");
    start.className = "start";
    start.style.left = `${x1}px`;
    start.style.top = `${y1}px`;

    for (let point of wordObj["path"]) {
        let y2 = point[0];
        let x2 = point[1];

        // highlighting
        board.children[y2 * 4 + x2].className += " highlight";

        x2 = rect.left + x2 * 50 + 25;
        y2 = rect.top + y2 * 50 + 25;

        let line = drawLine(x1, y1, x2, y2);
        board.appendChild(line);

        x1 = x2;
        y1 = y2;
    }
    board.appendChild(start);
};

// input
let textBox = document.createElement("input");
textBox.setAttribute("type", "text");
textBox.placeholder = "Enter board state";

// textBox.style.position = "relative";
textBox.style.top = "30px";

document.body.appendChild(textBox);
textBox.addEventListener("input", (e) => {
    board = [
        ["", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
    ];
    let value = textBox.value;
    let index = 0;
    boardState.setAttribute("state", "");

    for (let char of value) {
        char = char.toLowerCase();
        if ("abcdefghijklmnopqrstuvwxyz".includes(char)) {
            let row = parseInt(index / 4);
            let col = index % 4;
            index++;
            board[row][col] = char;
            boardState.setAttribute("state", boardState.getAttribute("state") + char);
        }
    }
    compute();
    return;
});

const compute = () => {
    // clean up
    try {
        document.body.removeChild(document.getElementsByClassName("moves")[0]);
        document.body.removeChild(document.getElementsByTagName("h1")[0]);
    } catch (error) { }

    let paths = solver();
    let moves = document.createElement("div");
    moves.className = "moves";
    document.body.appendChild(moves);
    paths = paths.sort((a, b) => (a.points > b.points ? -1 : 1));
    let sum = 0;
    for (let i of paths) {
        sum += i.points;
        i["path"] = JSON.parse(i["path"]);
        let board = createBoard(boardState.getAttribute("state"));
        moves.appendChild(board);

        let word = document.createElement("a");
        word.innerHTML = `${i["word"]} - ${i["points"]}`;
        board.appendChild(word);

        drawLines(board, i);
    }
    let max = document.createElement("h1");
    const nFormat = new Intl.NumberFormat();
    max.innerHTML = `Maximum Score: ${nFormat.format(sum)}`;
    max.style.top = "60px";
    document.body.appendChild(max);
};
textBox.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        // compute();
    }
});


// input board
let boardState = createBoard("");
// document.body.appendChild(boardState);
