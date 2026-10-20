# Smart Peer Companion user guide

Draft for the final delivery pack, written on 18 October 2026 from the pages and
buttons in the current code. Screenshots still need to be added where marked.
Check every step once on the live site before this goes to the sponsor.

Smart Peer Companion helps you study from your own lecture notes. You upload a
PDF, then ask questions about it and get answers that point back to the page they
came from. You can also study with classmates in groups and see your notes as a
map of connected ideas.

## 1. Before you start

* You need an account. Choose **Sign up** on the login screen, then log in.
* Notes must be **PDF** files of **10 MB or less**. Text based lecture slides and
  typed notes work best. Scanned pages with no real text will not give good
  answers.
* The AI can make mistakes. Always check important answers against your notes.
  The sources under each answer are there to help you do that.
* You are logged out automatically after a period of time. If a message says your session has
  ended, log in again. Your notes and chats are still there.
* Only upload material you are allowed to share. See section 9 for what happens
  to your data.

## 2. The menu

The menu on the left has these places.

| Menu item | What it is for |
| --- | --- |
| Dashboard | Your recent notes and quick buttons to upload, ask the AI, or open the knowledge graph |
| Notes | Opens two links, **Upload Notes** and **My Notes** |
| AI Assistant | Ask questions about your notes |
| Study Groups | Opens two links, **Public Groups** and **Private Groups**, which are your own groups of each kind |
| Knowledge Graph | See the ideas in a note as a connected map |

The Profile and Settings links at the bottom of the menu do not open a working
page yet. See section 10.

## 3. Upload a note

1. Open **Upload Notes** from the Dashboard quick buttons, or from **Notes** in
   the menu.
2. Type a **Note title**, for example "Week 4 Data Structures".
3. Drag your PDF into the box, or choose **Browse Files**.
4. Select **Upload PDF**.
5. Watch the status under **Recent Uploads**. It moves from **Queued** to
   **Processing** with a percentage, and ends at **Ready**. Large PDFs with many
   pictures can take a few minutes. You can leave the page and come back.
6. If it says **Failed**, check that the file is a real PDF with text and is
   under 10 MB, then try again.

You can ask questions as soon as the status says **Ready**.

[Screenshot placeholder. Upload Notes page with a note in Processing.]

## 4. Manage your notes

Open **Notes** then **My Notes**. Each note shows its status. Choose
**View Details** to see more about it, and **Delete** to remove it. Deleting a
note removes it from your list and from your AI answers.

## 5. Ask the AI Assistant

1. Open **AI Assistant**.
2. Select **New Conversation**. Rename it later if you like.
3. Type your question in the box that says "Ask a question about your study
   materials..." and press send.
4. Read the answer. Under it you will see the source notes and the page numbers
   the answer was based on.

You can also attach a PDF straight from the chat box with the paperclip button.

Tips for better answers

* Ask about one thing at a time, for example "What is the difference between a
  stack and a queue in my Week 4 notes?"
* Be specific. Names, formulas and topics from the notes help the AI find the
  right pages.
* You can ask a follow up like "Can you put that in bullet points?" or "Explain
  the second point more simply."
* If the notes do not cover your question, the AI will say so instead of
  guessing. That is on purpose.

Each conversation keeps its own history. Use a separate conversation for each
subject so answers do not mix. You can delete a conversation from the list.

[Screenshot placeholder. An answer with its sources.]

## 6. Study groups

Open **Study Groups**. There are two views at the top.

* **Discover Public** shows public groups you can search and join.
* **My Groups** shows the groups you belong to. Use the buttons All, Public,
  Private and Owned to narrow the list. The **Public Groups** and **Private
  Groups** links in the menu open My Groups with that button already chosen.

Create a group

1. Select **Create Group**.
2. Give it a name and a description.
3. Choose **Visibility**. Public groups can be found and joined by anyone.
   Private groups can only be joined when the owner or an admin invites you. The
   setting starts on Public, so change it if you want a private group.
4. Set the **Maximum members** and save.

Inside a group

* Each group has channels for different topics. Pick a channel to read and send
  messages.
* Attach a PDF in a channel so the group can ask the AI about it. Wait for
  "PDF ready for AI questions" before you ask.
* To ask the AI in a channel, type `@` and choose one of four helpers.

| Helper | What it does |
| --- | --- |
| Companion | Answers a question using the group's PDF |
| Summarizer | Summarises a section or topic |
| QuizMaster | Asks you quiz questions and does not give the answers away |
| Facilitator | Asks guiding questions to help the group think it through |

After you pick a helper, a bar appears above the message box. Use it to choose
how the answer looks, as **Paragraph**, **Bullet points** or **Table**. The AI
only reads a group message when someone asks it using `@`.

[Screenshot placeholder. A channel with the helper bar showing.]

## 7. Knowledge Graph

The Knowledge Graph shows the main ideas in one of your notes and how they link.

1. Open **Knowledge Graph**.
2. Choose a note from the list at the top. Only notes that are **Ready** appear.
3. Wait for the graph to build. The first time can take a moment.
4. Select an idea in the map to read its details.
5. Use the reload button if the graph does not appear.

Use it to see what connects to what before an exam, or to find a topic you have
not studied yet.

[Screenshot placeholder. A graph with one idea selected.]

## 8. Log out

Use the log out button at the top right when you finish, especially on a shared
computer.

## 9. Your data and privacy

* Your account, notes and chats are kept on a university project server and are
  deleted when the evaluation ends on **[date to be confirmed]**.
* To answer a question, the system sends your question, the matching passages
  from your notes, and your recent messages in that chat to an external AI
  service. Pictures inside PDFs are also sent to be described.
* Do not upload anything private or confidential.
* Deleting a note or a chat hides it straight away. It is fully erased at the end
  of the evaluation.

The full explanation is in
`Project_Documents/04_Compliance_and_Ethics/DATA_HANDLING_AND_DELETION.md`.

## 10. Known limits

* Only PDF files are supported.
* The Profile and Settings links in the menu lead to a "page not found" screen.
* There is no way to delete your account yourself yet. Ask the team.
* Answers can be wrong or incomplete, so check the sources.
* Very large PDFs take longer to prepare.

## 11. Troubleshooting

| What you see | What to try |
| --- | --- |
| The upload stays on Queued for a long time | Wait a few minutes. If nothing moves, tell the team. The worker may need a restart |
| The note says Failed | Check the file is a text based PDF under 10 MB, then upload it again |
| The AI says it cannot find the answer in your notes | Check the right note is Ready, or rephrase using words from the notes. The topic may not be in your notes |
| You were sent back to the login screen | Your session ended. Log in again |
| The AI stops replying | Wait a minute and try again. If it keeps happening, tell the team the time it happened |
| A private group shows up where you did not expect | Open the group and check its visibility badge. Tell the team if it is wrong |

## 12. Getting help

Tell the team on the project channel, and include what you clicked, what you
expected, what happened, and roughly what time it was. A screenshot helps. The
team uses this to fix problems quickly.
