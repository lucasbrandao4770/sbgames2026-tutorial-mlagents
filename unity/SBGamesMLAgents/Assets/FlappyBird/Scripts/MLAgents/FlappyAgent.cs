using Unity.MLAgents;
using Unity.MLAgents.Sensors;
using Unity.MLAgents.Actuators;
using UnityEngine;
using UnityEngine.InputSystem;


public class FlappyAgent : Agent
{
    private FlappyScript flappy;

    public override void Initialize()
    {
        flappy = GetComponent<FlappyScript>();

        // Subscribe to the collision event
        flappy.OnCollision += HandleFlappyCollision;
    }

    private void HandleFlappyCollision(object sender, FlappyScript.CollisionEventArgs e)
    {
        if (e.Tag == "Pipeblank")
        {
            AddReward(1.0f); // Reward for passing a checkpoint
        }
        else if (e.Tag == "Pipe" || e.Tag == "Wall")
        {
            AddReward(-1.0f); // Penalty for hitting an obstacle
            //EndEpisode(); // The episode is ended when the scene is reset
        }
    }

    public override void CollectObservations(VectorSensor sensor)
    {
        // Add bird's normalized height
        float normalizedHeight = Mathf.Clamp(flappy.GetHeight() / 10f, 0f, 1f); // Assuming 10 is the max height
        sensor.AddObservation(normalizedHeight);

        // Add bird's normalized velocity
        Vector2 velocity = flappy.GetVelocity();
        sensor.AddObservation(velocity.x / 5f); // Assuming max X speed is 5
        sensor.AddObservation(velocity.y / 5f); // Assuming max Y speed is 5

        // Add distance to the next pipe (normalized)
        float distanceToPipe = GetDistanceToNextPipe();
        sensor.AddObservation(distanceToPipe / 10f); // Assuming 10 is the max distance to the next pipe
    }

    // Perform actions based on decisions made by the model
    public override void OnActionReceived(ActionBuffers actions)
    {
        bool doJump = actions.DiscreteActions[0] == 1;

        if (doJump) {
            flappy.Jump();
        }
    }

    public override void Heuristic(in ActionBuffers actionsOut)
    {
        ActionSegment<int> discreteActions = actionsOut.DiscreteActions;

        // Default action: no jump (0)
        discreteActions[0] = 0;

        // Check for manual input to trigger a jump (set to 1)
        if (Keyboard.current.spaceKey.IsPressed())
        {
            discreteActions[0] = 1;
        }
    }

    private float GetDistanceToNextPipe()
    {
        GameObject[] pipes = GameObject.FindGameObjectsWithTag("Pipeblank");
        float birdX = transform.position.x;

        float nearestDistance = float.MaxValue;
        foreach (GameObject pipe in pipes)
        {
            float pipeX = pipe.transform.position.x;
            if (pipeX > birdX) // Only consider pipes ahead of the bird
            {
                float distance = pipeX - birdX;
                if (distance < nearestDistance)
                {
                    nearestDistance = distance;
                }
            }
        }

        return nearestDistance == float.MaxValue ? 10f : nearestDistance; // Default to max distance if no pipes are found
    }
}
