export default function AssistantMessage({
  message,
  notesTracks,
  notesTrack,
  onNotesTrackChange,
  onSaveToNotes,
  notesSaveState,
}) {
  const saveState = notesSaveState || "";

  if (message.role !== "assistant") {
    return <div className="message user">{message.text}</div>;
  }

  return (
    <div className="message assistant">
      <div className="message-body">{message.text}</div>
      {message.text ? (
        <div className="message-actions note-actions">
          <select
            aria-label="Notes folder"
            onChange={(event) => onNotesTrackChange(event.target.value)}
            value={notesTrack}
          >
            {(notesTracks.length ? notesTracks : [{ id: notesTrack || "from-coding-agent" }]).map((track) => (
              <option key={track.id} value={track.id}>
                {track.id}
              </option>
            ))}
          </select>
          <button disabled={saveState === "saving"} onClick={() => onSaveToNotes(message)} type="button">
            {saveState === "saving"
              ? "Saving..."
              : saveState === "saved"
                ? "Saved to Notes"
                : "Save to Notes"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
