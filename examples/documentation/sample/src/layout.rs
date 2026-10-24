/// Items are measured once and the sizes are reused until the width changes (backlog 3).
/// Decisions that bind this module are listed in docs/decisions.md.
pub fn row_height(measured: &[u32], index: usize) -> u32 {
    // An index past the end reuses the last measured row, so a growing list never panics.
    *measured.get(index).or(measured.last()).unwrap_or(&0)
}
