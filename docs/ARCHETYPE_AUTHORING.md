# Archetype & Composition Authoring Guide

## Archetype

An Archetype says **what the slide is doing semantically**: benchmark, root cause, decision, risk, research method, etc.

Each Archetype maps to:
- a semantic family;
- a Composition;
- a renderer;
- a concise information intent.

## Composition

A Composition says **how the information is arranged**. Add one only when an existing visual grammar cannot express the information without distortion.

This separation prevents renderer explosion: `before-after`, `win-loss` and many benchmarks can share comparison grammar.
