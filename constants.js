export let scrabbleWords;
await fetch("./utils/words.txt")
    .then((response) => response.text())
    .then((data) => {
    scrabbleWords = data.split("\n");
});
