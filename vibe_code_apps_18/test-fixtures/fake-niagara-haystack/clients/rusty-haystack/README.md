# rusty-haystack client probe

This pinned Rust client exercises both history shapes against the fake Niagara
fixture:

```sh
cargo run --release -- --url http://192.168.204.12:8080/api --mode single
cargo run --release -- --url http://192.168.204.12:8080/api --mode bulk
```

`single` uses `HaystackClient::his_read`. `bulk` uses the generic `call` API to
send the standard multi-point request: `range` in grid metadata and one `id`
row per discovered point. The expected response is a wide grid with `ts` plus
`v0`, `v1`, and so on. This makes the bulk probe representative of a daily
native-history backfill before rows are normalized into SQL.

The dependency is pinned to a tested rusty-haystack commit. Update the pin only
with a live single and bulk test plus a committed `Cargo.lock` refresh.
