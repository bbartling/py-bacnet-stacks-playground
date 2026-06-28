use anyhow::{Context, Result};
use std::net::UdpSocket;
use std::time::Duration;

/// Placeholder Who-Is: binds UDP socket and documents next steps.
/// Replace with rusty-bacnet discovery when you reach Day 41–45.
pub fn run(bind: &str, filter_device: Option<u32>) -> Result<()> {
    let socket = UdpSocket::bind(bind).with_context(|| format!("bind {bind}"))?;
    socket.set_read_timeout(Some(Duration::from_secs(3)))?;

    eprintln!("discover-and-poll: bound on {bind}");
    eprintln!("TODO Day 41+: send BACnet Who-Is via rusty-bacnet and parse I-Am.");
    eprintln!("Lab hint: capture with ../../lab-scripts/capture_pcap.sh day46-bacnet 'udp port 47808'");

    if let Some(id) = filter_device {
        eprintln!("filter device id: {id}");
    }

    // Stub: prove UDP path works on bench VLAN
    let stub = format!(
        "stub,device_id=5007,addr=192.168.204.200:47808,note=replace_with_I-Am"
    );
    println!("{stub}");

    if bind.contains("127.0.0.1") {
        eprintln!("warning: BACnet field traffic usually needs 0.0.0.0:47808 on your edge NIC");
    }

    Ok(())
}
