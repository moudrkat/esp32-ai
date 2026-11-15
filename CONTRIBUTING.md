# Contributing

Yes, please. This is a fork of [slvDev/esp32-ai](https://github.com/slvDev/esp32-ai); what is new here is the model that writes programs for the screen (`research/oled/`). Fixes to the runtime itself belong upstream.

```
PYTHONPATH=src:. pytest tests
```

- The easiest way to help needs no code: type 20 requests the way you'd say them and tell me what it drew. My own test sentences are suspiciously polite.
- A new shape or animation is one function in `research/oled/gen.py`. The interpreter checks every program before it is kept, so you can't break the chip. You can only confuse it.
- More ideas: [the open questions](https://github.com/moudrkat/tell-me).

I answer within a day. The chip takes five seconds, but it only does houses.
