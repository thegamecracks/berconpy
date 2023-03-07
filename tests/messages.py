# First message triggers on_login()
on_admin_login = "RCon admin #{id} ({ip}:{port}) logged in"

# Triggers on_admin_message
on_admin_announcement = "RCon admin #{id}: (Global) {message}"
on_admin_whisper = "RCon admin #{id}: (To {name}) {message}"

# Caching
on_player_connect = "Player #{id} {name} ({addr}) connected"
on_player_guid = "Player #{id} {name} - BE GUID: {guid}"
on_player_verify_guid = "Verified GUID ({guid}) of player #{id} {name}"
on_player_disconnect = "Player #{id} {name} disconnected"

# Player must be in cache for this
on_player_message = "({channel}) {name}: Hello world!"
