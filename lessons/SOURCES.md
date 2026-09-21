# Primary references and reading tasks

[Course index](INDEX.md) · [Lab guide](LAB_GUIDE.md)

Use these as references while implementing, not as assignments to read whole books first. Sources were consulted while revising the course on 2026-09-21; APIs and OS behavior can change. Pin dependencies for reproducible work. The classroom formats are defined in [WIRE_FORMATS.md](WIRE_FORMATS.md); real protocol rules come from their specifications.

## Week 1

[The Rust Book: Getting Started](https://doc.rust-lang.org/book/ch01-00-getting-started.html), [common concepts](https://doc.rust-lang.org/book/ch03-00-common-programming-concepts.html), and [collections](https://doc.rust-lang.org/book/ch08-00-common-collections.html). Read only the features used today. Explain values, mutation, UTF-8 and safe lookup in your own words.

## Week 2

[Control flow](https://doc.rust-lang.org/book/ch03-05-control-flow.html), [HashMap](https://doc.rust-lang.org/std/collections/struct.HashMap.html), and [HashSet](https://doc.rust-lang.org/std/collections/struct.HashSet.html). Identify ordering guarantees and missing-key behavior before designing report tests.

## Week 3

[Modules](https://doc.rust-lang.org/book/ch07-02-defining-modules-to-control-scope-and-privacy.html), [recoverable errors](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html), and [ownership](https://doc.rust-lang.org/book/ch04-00-understanding-ownership.html). Trace one owned input from file read to result; distinguish absence from failure.

## Week 4

[Structs](https://doc.rust-lang.org/book/ch05-00-structs.html), [enums](https://doc.rust-lang.org/book/ch06-00-enums.html), [lifetimes](https://doc.rust-lang.org/book/ch10-03-lifetime-syntax.html), [Read](https://doc.rust-lang.org/std/io/trait.Read.html), [Write](https://doc.rust-lang.org/std/io/trait.Write.html), and [clap derive tutorial](https://docs.rs/clap/latest/clap/_derive/_tutorial/index.html). Use public interfaces and deliberate error contracts; do not turn every reference example into a project dependency.

## Week 5

[IPv4, RFC 791](https://www.rfc-editor.org/rfc/rfc791), [IPv6, RFC 8200](https://www.rfc-editor.org/rfc/rfc8200), [Neighbor Discovery, RFC 4861](https://www.rfc-editor.org/rfc/rfc4861), [SLAAC, RFC 4862](https://www.rfc-editor.org/rfc/rfc4862), and [Rust networking types](https://doc.rust-lang.org/std/net/). Read address/header and neighbor/route procedures selectively. A prefix computation is not a replacement for an OS route table.

## Week 6

[Wireshark User's Guide](https://www.wireshark.org/docs/wsug_html_chunked/), [UDP, RFC 768](https://www.rfc-editor.org/rfc/rfc768), [TCP, RFC 9293](https://www.rfc-editor.org/rfc/rfc9293), and the IP specifications above. Compare fields with a decoder while retaining capture metadata and its limitations. For checksum/offload questions, inspect the capture guide and actual NIC configuration before declaring a corrupt sender.

## Week 7

[Rust UdpSocket](https://doc.rust-lang.org/std/net/struct.UdpSocket.html), [DNS, RFC 1035](https://www.rfc-editor.org/rfc/rfc1035), and [DNS clarifications, RFC 2181](https://www.rfc-editor.org/rfc/rfc2181). Check receive-buffer behavior and compression-name rules. The course's field messenger has no security/authentication or general discovery standard claim.

## Week 8

[Rust TcpStream](https://doc.rust-lang.org/std/net/struct.TcpStream.html), [TcpListener](https://doc.rust-lang.org/std/net/struct.TcpListener.html), [TCP specification](https://www.rfc-editor.org/rfc/rfc9293), and [Tokio framing explanation](https://tokio.rs/tokio/tutorial/framing). Learn partial I/O on blocking streams before converting code to async. Separate EOF, reset and timeout.

## Week 9

[Tokio tutorial](https://tokio.rs/tokio/tutorial), [select and cancellation](https://tokio.rs/tokio/tutorial/select), [graceful shutdown](https://tokio.rs/tokio/topics/shutdown), and [copy_bidirectional](https://docs.rs/tokio/latest/tokio/io/fn.copy_bidirectional.html). Inspect exact primitive behavior in the version selected by your Cargo.lock. Half-close and error behavior are public contracts worth testing even when a library handles copying.

## Week 10

[Modbus Organization specifications](https://www.modbus.org/modbus-specifications): use the application protocol, TCP/IP implementation guide and serial-line guide appropriate to the exercise. [Application protocol PDF](https://www.modbus.org/file/secure/modbusprotocolspecification.pdf) provides function and exception layouts. Read function 03 plus data encoding first; use the serial guide for RTU CRC/timing, not a TCP tutorial.

## Week 11

[rusty-bacnet upstream](https://github.com/jscott3201/rusty-bacnet), its actual pinned source/tests/examples, and the applicable ASHRAE 135 standard/addenda through [BACnet International/ASHRAE resources](https://bacnet.org/). The destination repo's `config/upstream-lock.toml` is the starting revision, not a promise that the upstream default branch has identical APIs. An independent implementation such as [BACpypes3](https://bacpypes3.readthedocs.io/en/latest/) is useful as an optional external oracle.

## Week 12

Use the applicable ASHRAE 135 application-service/segmentation procedures and pinned rusty-bacnet tests. The [Day 81 model contract](WIRE_FORMATS.md#segmentation-simulator) explicitly limits the simulator. Trace timer ownership and peer capability in actual code before a live test. COV and segmentation support must be demonstrated for the chosen revision and peer.

## Week 13

Use BACnet network-layer and BACnet/IP procedures, plus the destination router's architecture/testing docs. Read [Linux network namespaces](https://man7.org/linux/man-pages/man7/network_namespaces.7.html) and [ip-netns](https://man7.org/linux/man-pages/man8/ip-netns.8.html) for the test bed. BACnet/IPv6 and BACnet/SC are distinct protocol/support questions; use applicable standard material and actual implementation evidence.

## Week 14

[Raspberry Pi configuration](https://www.raspberrypi.com/documentation/computers/configuration.html), [NetworkManager connection properties](https://networkmanager.dev/docs/api/latest/nm-settings-nmcli.html), [nmcli](https://networkmanager.dev/docs/api/latest/nmcli.html), [DHCPv4, RFC 2131](https://www.rfc-editor.org/rfc/rfc2131), [DHCP options, RFC 2132](https://www.rfc-editor.org/rfc/rfc2132), and [nftables documentation](https://wiki.nftables.org/wiki-nftables/index.php/Main_Page). Match instructions to actual hardware/OS. Inspect shared-mode service ownership before combining tutorials.

## Week 15

Use the Modbus serial guide, applicable BACnet MS/TP procedures, the pinned upstream frame/CRC tests and the actual adapter manual. In the destination repo, read `docs/hardware/WAVESHARE_USB_RS485_C.md`, `docs/TESTING.md`, and current hold/evidence notes. PTY and host-read timestamps are not physical bus certification.

## Week 16

Start with `/home/ben/Desktop/diy-bacnet-router/AGENTS.md` and its required linked documents, then actual source call sites. For management networking: [HTTP semantics, RFC 9110](https://www.rfc-editor.org/rfc/rfc9110), [HTTP/1.1 framing, RFC 9112](https://www.rfc-editor.org/rfc/rfc9112), [Rustls](https://docs.rs/rustls/latest/rustls/), and [WebSocket, RFC 6455](https://www.rfc-editor.org/rfc/rfc6455). Use maintained libraries for full HTTP/TLS; test limits and failure behavior at your application boundary.

## Packt as a companion

[Network Programming with Rust](https://github.com/PacktPublishing/Network-Programming-with-Rust/tree/master) provides useful historical project ideas. See the chapter crosswalk in [INDEX.md](INDEX.md#reading-packt-with-current-rust). Rebuild the intent against current APIs; do not make reviving old manifests a prerequisite. The new course adds deeper packet interpretation, IPv6, failure experiments, BACnet routing and appliance evidence.
