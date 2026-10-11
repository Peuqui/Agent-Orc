Set shell = CreateObject("Wscript.Shell")
wsl = """C:\Program Files\WSL\wsl.exe"" -d Ubuntu-24.04"

' Keeps the distribution running.
shell.Run wsl & " --exec sleep infinity", 0, False

' After the start, as root: WSLg mounts its own directory over /run/user/1000 after systemd has
' put its sockets there, so `systemctl --user` fails ("Failed to connect to bus"). Restarting the
' user manager puts them into the visible layer; WSLg stays. Waits up to 60 s for the second
' layer, restarts only if the bus is hidden (no agent runs at the start), logs what it did.
fix = "L=/var/log/wsl-user-bus-fix.log; n() { grep -c ' /run/user/1000 ' /proc/self/mountinfo; }; " & _
      "for i in $(seq 1 60); do [ $(n) -ge 2 ] && break; sleep 1; done; " & _
      "if [ $(n) -ge 2 ] && [ ! -S /run/user/1000/bus ]; then " & _
      "systemctl restart user@1000; echo $(date +%F_%T) restarted layers=$(n) >> $L; " & _
      "else echo $(date +%F_%T) nothing-to-do layers=$(n) >> $L; fi"
shell.Run wsl & " -u root --exec bash -c """ & fix & """", 0, False
