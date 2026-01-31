#!/usr/bin/env python3
"""
Simple iTerm2 Control Demo
==========================
A minimal example showing how to create and monitor iTerm2 sessions.

This is a simpler alternative to controller.py that demonstrates
the core concepts without the full TUI framework.

Requirements:
    pip install iterm2

Usage:
    python simple_demo.py
"""

import asyncio
import iterm2


async def create_split_layout(connection):
    """Create a window with multiple panes in a grid layout."""
    print("Creating split pane layout...")

    app = await iterm2.async_get_app(connection)
    window = app.current_terminal_window

    if window is None:
        print("No iTerm2 window available. Creating one...")
        window = await iterm2.Window.async_create(connection)

    # Create a new tab for our layout
    tab = await window.async_create_tab()
    main_session = tab.current_session

    # Set up a 2x2 grid
    # Start with the main session in top-left
    top_left = main_session

    # Split right to create top-right
    top_right = await top_left.async_split_pane(vertical=True)

    # Split top-left down to create bottom-left
    bottom_left = await top_left.async_split_pane(vertical=False)

    # Split top-right down to create bottom-right
    bottom_right = await top_right.async_split_pane(vertical=False)

    # Run different commands in each pane
    commands = [
        (top_left, "echo '📁 Top Left: File Watcher' && while true; do echo \"$(date '+%H:%M:%S'): Watching...\"; sleep 3; done"),
        (top_right, "echo '🚀 Top Right: Server' && echo 'Starting server on :3000...' && sleep 2 && while true; do echo \"$(date '+%H:%M:%S'): Request handled\"; sleep 2; done"),
        (bottom_left, "echo '📊 Bottom Left: System Stats' && while true; do echo \"CPU: $((RANDOM % 100))% | MEM: $((RANDOM % 100))% | $(date '+%H:%M:%S')\"; sleep 2; done"),
        (bottom_right, "echo '📝 Bottom Right: Logs' && while true; do echo \"[$(date '+%H:%M:%S')] INFO: Log entry $((RANDOM % 1000))\"; sleep 1; done"),
    ]

    for session, cmd in commands:
        await session.async_send_text(f"{cmd}\n")

    print("Layout created with 4 panes!")
    return [top_left, top_right, bottom_left, bottom_right]


async def monitor_sessions(connection, sessions, duration=30):
    """Monitor multiple sessions and print their output."""
    print(f"\nMonitoring {len(sessions)} sessions for {duration} seconds...")
    print("=" * 60)

    async def monitor_one(session, index):
        """Monitor a single session."""
        try:
            async with session.get_screen_streamer() as streamer:
                while True:
                    contents = await streamer.async_get()
                    if contents:
                        # Get last line of output
                        last_line = ""
                        for i in range(contents.number_of_lines - 1, -1, -1):
                            line = contents.line(i).string.strip()
                            if line:
                                last_line = line
                                break

                        if last_line:
                            print(f"[Pane {index}] {last_line[:60]}")

                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    # Start monitoring all sessions
    tasks = [
        asyncio.create_task(monitor_one(session, i))
        for i, session in enumerate(sessions)
    ]

    # Let them run for a while
    await asyncio.sleep(duration)

    # Cancel all monitors
    for task in tasks:
        task.cancel()

    print("=" * 60)
    print("Monitoring complete!")


async def demo_notifications(connection):
    """Demonstrate subscribing to iTerm2 notifications."""
    print("\nSetting up notification handlers...")

    # Track notifications
    events = []

    async def on_new_session(conn, notification):
        msg = f"New session created: {notification.session_id}"
        events.append(msg)
        print(f"📢 {msg}")

    async def on_terminate(conn, notification):
        msg = f"Session terminated: {notification.session_id}"
        events.append(msg)
        print(f"📢 {msg}")

    async def on_layout_change(conn, notification):
        msg = "Layout changed!"
        events.append(msg)
        print(f"📢 {msg}")

    # Subscribe to events
    await iterm2.async_subscribe_to_new_session_notification(
        connection, on_new_session
    )
    await iterm2.async_subscribe_to_terminate_session_notification(
        connection, on_terminate
    )
    await iterm2.async_subscribe_to_layout_change_notification(
        connection, on_layout_change
    )

    print("Subscribed to: new session, terminate, layout change")
    return events


async def interactive_menu(connection):
    """Simple interactive menu to control iTerm2."""
    app = await iterm2.async_get_app(connection)

    while True:
        print("\n" + "=" * 40)
        print("iTerm2 Controller Menu")
        print("=" * 40)
        print("1. Create new tab")
        print("2. Create split layout (2x2)")
        print("3. List all sessions")
        print("4. Send command to current session")
        print("5. Monitor current session")
        print("6. Close current tab")
        print("q. Quit")
        print("-" * 40)

        choice = input("Choice: ").strip().lower()

        if choice == "q":
            print("Goodbye!")
            break

        elif choice == "1":
            window = app.current_terminal_window
            if window:
                tab = await window.async_create_tab()
                print(f"Created new tab with session: {tab.current_session.session_id}")
            else:
                print("No window available")

        elif choice == "2":
            sessions = await create_split_layout(connection)
            input("Press Enter to start monitoring (30s)...")
            await monitor_sessions(connection, sessions, duration=15)

        elif choice == "3":
            print("\nAll sessions:")
            for window in app.windows:
                print(f"  Window: {window.window_id}")
                for tab in window.tabs:
                    print(f"    Tab: {tab.tab_id}")
                    for session in tab.sessions:
                        print(f"      Session: {session.session_id}")

        elif choice == "4":
            window = app.current_terminal_window
            if window:
                session = window.current_tab.current_session
                cmd = input("Command to send: ")
                await session.async_send_text(f"{cmd}\n")
                print("Command sent!")
            else:
                print("No active session")

        elif choice == "5":
            window = app.current_terminal_window
            if window:
                session = window.current_tab.current_session
                print("Monitoring for 10 seconds...")
                await monitor_sessions(connection, [session], duration=10)
            else:
                print("No active session")

        elif choice == "6":
            window = app.current_terminal_window
            if window and window.current_tab:
                await window.current_tab.async_close()
                print("Tab closed")
            else:
                print("No tab to close")


async def main(connection):
    """Main entry point."""
    print("=" * 60)
    print("iTerm2 Control Demo")
    print("=" * 60)

    # Set up notifications in background
    await demo_notifications(connection)

    # Run interactive menu
    await interactive_menu(connection)


if __name__ == "__main__":
    try:
        iterm2.run_until_complete(main)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure:")
        print("  1. You're running this inside iTerm2")
        print("  2. Python API is enabled:")
        print("     Preferences > General > Magic > Enable Python API")
