#!/usr/bin/env node
'use strict';
const fs=require('fs');
const {analyze}=require('../analytics');

const input=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(analyze(input)));
