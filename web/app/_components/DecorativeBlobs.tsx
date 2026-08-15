// design.md §3/§6 — depth via overlapping blurred pastel blobs rather than
// gradients, drifting gently (float loop) to set the "digital living room"
// atmosphere. Shared by the marketing hero, marketing closing CTA, and the
// exam's pre-instructions screen so the background treatment reads as one
// continuous world across the hand-off from marketing site into the app.
// Renders into whatever `relative overflow-hidden` container it's placed in.
export function DecorativeBlobs() {
  return (
    <>
      <div
        aria-hidden="true"
        className="absolute -left-24 top-10 h-72 w-72 animate-float rounded-full bg-blob-pink opacity-60 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="absolute -right-20 bottom-10 h-80 w-80 animate-float-delayed rounded-full bg-blob-lavender opacity-60 blur-3xl"
      />
    </>
  );
}
