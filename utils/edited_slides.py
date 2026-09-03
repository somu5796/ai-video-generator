import os


def find_edited_states_for_scene(slides_dir: str, scene_number: int, expected_count: int) -> list:
    """
    Looks in slides_dir for a COMPLETE set of hand-edited build-state
    images for one scene, named to match exactly what HtmlRenderer
    would have generated itself:

        scene_{scene_number:02d}_state_{i:02d}.png   for i = 1..expected_count

    expected_count comes from calling the renderer's own build_states()
    on the scene — the number of states (and their hold_durations) is
    still computed from the script's timing, same as always. Only the
    IMAGE for each state is swapped for the user's edited version.

    Returns the ordered list of image paths if ALL expected files exist,
    otherwise None — callers should fall back to auto-rendering that
    scene rather than guessing at a partial/mismatched set. This makes
    "mixed mode" safe: some scenes hand-edited, others auto-generated,
    in the same run.
    """
    if not slides_dir or not os.path.isdir(slides_dir):
        return None

    paths = []
    for i in range(1, expected_count + 1):
        path = os.path.join(slides_dir, f"scene_{scene_number:02d}_state_{i:02d}.png")
        if not os.path.exists(path):
            return None
        paths.append(path)
    return paths


def expected_state_filenames(scene_number: int, state_count: int) -> list:
    """
    Returns the filenames deck_agent will look for if you choose to
    hand-edit this scene's slides — used by deck_preview_agent to tell
    you exactly what to name your exports before you go edit anything.
    """
    return [
        f"scene_{scene_number:02d}_state_{i:02d}.png"
        for i in range(1, state_count + 1)
    ]
