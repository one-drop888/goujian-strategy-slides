const { chooseStoryline } = require('./storyline');
function classify(text='') { return chooseStoryline(text); }
module.exports={ classify, chooseStoryline };
