import time
import random
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import UserStatusOnline, UserStatusRecently, UserStatusOffline, Channel, Chat
from telethon.errors.rpcerrorlist import (
    PeerFloodError,
    UserPrivacyRestrictedError,
    UserNotMutualContactError,
    UserChannelsTooMuchError,
    ChatAdminRequiredError,
    UserAlreadyParticipantError
)

# --- CONFIGURATION ---
# Obtain these from my.telegram.org
api_id = 12345678
api_hash = 'YOUR_API_HASH'
phone = '+1234567890'  # Your phone number with country code

# Delay between adding members (in seconds).
# A range is used to simulate more human-like behavior.
delay_range = (15, 30)

# The number of members to add before taking a longer break.
adds_before_break = 100
# The duration of the longer break (in seconds).
long_break_duration = 300

# --- SCRIPT ---

def display_chats(dialogs):
    """Displays a numbered list of chats."""
    for i, dialog in enumerate(dialogs):
        print(f"{i} - {dialog.name}")

def get_user_choice(prompt, upper_bound):
    """Gets and validates user input for chat selection."""
    while True:
        try:
            choice = int(input(prompt))
            if 0 <= choice < upper_bound:
                return choice
            else:
                print("Invalid number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    """Main function to run the script."""
    with TelegramClient(phone, api_id, api_hash) as client:
        print("--- Telegram Member Adder ---")

        dialogs = [d for d in client.get_dialogs() if d.is_group or d.is_channel]

        if not dialogs:
            print("You are not a part of any groups or channels.")
            return

        print("\nYour chats:")
        display_chats(dialogs)

        # Select the group to add members to
        my_group_index = get_user_choice(
            "\nEnter the number of the group to ADD members to: ", len(dialogs)
        )
        my_group = dialogs[my_group_index].entity

        # Select the target group to get members from
        print("\nSelect the target group to GET members from:")
        display_chats(dialogs)
        target_group_index = get_user_choice(
            "\nEnter the number of the target group: ", len(dialogs)
        )
        target_group = dialogs[target_group_index].entity

        # Fetch members from the target group
        print(f"\nFetching members from '{target_group.title}'...")
        target_members = client.get_participants(target_group, aggressive=True)
        print(f"✅ {len(target_members)} members fetched.")

        # Fetch existing members to avoid duplicates
        print(f"Checking existing members in '{my_group.title}'...")
        existing_members = client.get_participants(my_group, aggressive=True)
        existing_ids = {user.id for user in existing_members}
        print(f"ℹ️ Found {len(existing_ids)} existing members in your group.")

        # --- Member Addition ---
        print("\n🚀 Starting to add members...")
        added_count = 0
        for i, user in enumerate(target_members):
            if user.bot or user.deleted:
                continue

            if user.id in existing_ids:
                print(f"⏩ Skipped {user.first_name} (already in group)")
                continue

            try:
                print(f"➕ Adding {user.first_name} {user.last_name or ''}...")

                # Use the correct request based on group type
                if isinstance(my_group, Channel):
                    client(InviteToChannelRequest(my_group, [user]))
                elif isinstance(my_group, Chat):
                    client(AddChatUserRequest(my_group.id, user.id, fwd_limit=10))

                added_count += 1
                print(f"✅ Successfully added. Total added: {added_count}")
                existing_ids.add(user.id)

                # Take a long break after a certain number of additions
                if added_count > 0 and added_count % adds_before_break == 0:
                    print(f"\n-- Taking a long break for {long_break_duration} seconds --\n")
                    time.sleep(long_break_duration)

                # Regular delay between additions
                sleep_time = random.uniform(delay_range[0], delay_range[1])
                time.sleep(sleep_time)

            except UserAlreadyParticipantError:
                print("❌ User is already a participant.")
            except UserPrivacyRestrictedError:
                print("❌ Failed: User's privacy settings do not allow this.")
            except UserNotMutualContactError:
                print("❌ Failed: User is not a mutual contact.")
            except UserChannelsTooMuchError:
                print("❌ Failed: User has joined too many channels/supergroups.")
            except ChatAdminRequiredError:
                print("❌ Failed: Admin permissions are required to add users.")
                break  # Stop if we are not an admin
            except PeerFloodError as e:
                print(f"❌ Aborting due to PeerFloodError. Please wait for {e.seconds} seconds.")
                time.sleep(e.seconds)
            except Exception as e:
                print(f"❌ An unexpected error occurred: {e}")
                time.sleep(random.uniform(5, 10))

        print(f"\n✅ Done. Total members added: {added_count}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting gracefully.")
