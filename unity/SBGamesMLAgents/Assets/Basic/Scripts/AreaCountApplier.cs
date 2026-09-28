using Unity.MLAgents.Areas;
using UnityEngine;

/// <summary>
/// Applies the area count requested from the scene menu (SceneBoot.RequestedAreaCount) to this Basic
/// scene's TrainingAreaReplicator before it computes its grid in its own Awake (DefaultExecutionOrder -5;
/// this one runs at -100, so it always goes first). Lives on the same GameObject as the replicator.
/// Only matters without a trainer: with one connected, the replicator takes its area count from the
/// trainer's --num-areas handshake instead (Academy.Instance.NumAreas), and this becomes a harmless no-op.
/// </summary>
[DefaultExecutionOrder(-100)]
public class AreaCountApplier : MonoBehaviour
{
    void Awake()
    {
        var replicator = GetComponent<TrainingAreaReplicator>();
        if (replicator != null)
            replicator.numAreas = SceneBoot.RequestedAreaCount;
    }

    // Runs after every object's Awake/OnEnable, so the replicator (OnEnable) has already added its copies
    // in a standalone build. A simple, greppable log line proving how many areas actually ended up in the
    // scene, since TrainingAreaReplicator itself logs nothing. Reads numAreas back off the replicator
    // rather than SceneBoot.RequestedAreaCount, because a connected trainer's --num-areas overwrites the
    // component's value in TrainingAreaReplicator's own Awake (execution order -5, after this one's -100).
    void Start()
    {
        var replicator = GetComponent<TrainingAreaReplicator>();
        int agents = FindObjectsByType<MoveToGoalAgent>(FindObjectsSortMode.None).Length;
        Debug.Log("AreaCountApplier: numAreas=" + (replicator != null ? replicator.numAreas : -1) + ", " + agents + " agent(s) in the scene.");
    }
}
