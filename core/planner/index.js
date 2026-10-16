const { chooseStoryline } = require('./storyline');
const { recommendArchetype } = require('./visualization');
const { looksLikeTopicTitle, actionTitleScore } = require('./action-title');
const {resolveTitle}=require('./title');
module.exports={chooseStoryline,recommendArchetype,looksLikeTopicTitle,actionTitleScore,resolveTitle};
