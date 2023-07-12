let root = createNode(false);
import { scrabbleWords } from "./constants.js";

function createNode(isWord) {
    return {
        children: new Map(),
        isWord: isWord,
    };
}

function createLetterTree(wordList) {
    for (let word in wordList) {
        let currentNode = root;
        word = wordList[word];
        word = word.replace("\r", "");
        for (let i = 0; i < word.length; i++) {
            let letter = word[i];
            if (!currentNode.children.has(letter)) {
                currentNode.children.set(letter, createNode(false));
            }
            currentNode = currentNode.children.get(letter);
        }
        currentNode.isWord = true;
    }
    return root;
}

export function isWord(word) {
    let currentNode = root;
    for (let i = 0; i < word.length; i++) {
        let letter = word[i];
        if (!currentNode.children.has(letter)) {
            return false;
        }
        currentNode = currentNode.children.get(letter);
    }
    return currentNode.isWord;
}

export function lookupWord(partialWord) {
    let currentNode = root;
    for (let i = 0; i < partialWord.length; i++) {
        let letter = partialWord[i];
        if (!currentNode.children.has(letter)) {
            return undefined;
        }
        currentNode = currentNode.children.get(letter);
    }
    return currentNode;
}

export function initLetterTree() {
    createLetterTree(scrabbleWords);
    return root;
}
