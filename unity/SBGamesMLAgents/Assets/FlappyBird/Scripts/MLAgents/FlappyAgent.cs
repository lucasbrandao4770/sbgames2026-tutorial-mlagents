using Unity.MLAgents;
using Unity.MLAgents.Sensors;
using Unity.MLAgents.Actuators;
using UnityEngine;
using UnityEngine.InputSystem;


public class FlappyAgent : Agent
{
    private FlappyScript flappy;

    // Initialize() roda uma vez por instância do agente, quando ele é ativado pela primeira vez.
    // Como o jogo recarrega a cena a cada morte, um agente novo nasce e Initialize() roda a cada vida.
    // É o lugar certo para guardar referências e se inscrever em eventos, como abaixo.
    public override void Initialize()
    {
        flappy = GetComponent<FlappyScript>();

        // Subscribe to the collision event
        // A partir daqui, cada colisão com as tags Pipeblank, Pipe ou Wall chama HandleFlappyCollision.
        flappy.OnCollision += HandleFlappyCollision;
    }

    // HandleFlappyCollision não é um método do ciclo de vida do Agent: é o handler assinado acima.
    // É aqui que as colisões do jogo viram recompensa para o ML-Agents.
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
            // Sem EndEpisode() aqui, o episódio termina quando o GameObject do agente é destruído
            // junto com a cena (o ML-Agents fecha o episódio nesse momento) ou quando o agente
            // atinge o Max Step de 5000 passos configurado no Inspector.
        }
    }

    // CollectObservations roda a cada decisão pedida pelo Decision Requester.
    // Aqui o agente descreve o que consegue perceber do ambiente, sempre como números normalizados.
    // Essas quatro observações manuais se somam às da Ray Perception Sensor 2D configurada no objeto
    // filho "Rays": esse sensor não aparece neste script porque é um componente à parte, adicionado
    // direto no Inspector, não em código.
    public override void CollectObservations(VectorSensor sensor)
    {
        // Add bird's normalized height
        // Altura normalizada: ajuda o agente a saber se está perto do teto ou caindo demais.
        float normalizedHeight = Mathf.Clamp(flappy.GetHeight() / 10f, 0f, 1f); // Assuming 10 is the max height
        sensor.AddObservation(normalizedHeight);

        // Add bird's normalized velocity
        // Velocidade em X e Y: ajuda o agente a perceber para onde está indo, não só onde está.
        Vector2 velocity = flappy.GetVelocity();
        sensor.AddObservation(velocity.x / 5f); // Assuming max X speed is 5
        sensor.AddObservation(velocity.y / 5f); // Assuming max Y speed is 5

        // Add distance to the next pipe (normalized)
        // Distância até o próximo cano: dá noção de quando se preparar para o próximo vão.
        float distanceToPipe = GetDistanceToNextPipe();
        sensor.AddObservation(distanceToPipe / 10f); // Assuming 10 is the max distance to the next pipe
    }

    // Perform actions based on decisions made by the model
    // OnActionReceived roda a cada passo: o Decision Requester pede uma decisão a cada 5 passos e,
    // com Take Actions Between Decisions ligado, repete a última ação entre decisões. A ação vem da
    // política treinada, do treinador durante o treino, ou de Heuristic() abaixo.
    // A ação é um único ramo discreto com dois valores: 0 não bate asas, 1 bate asas.
    public override void OnActionReceived(ActionBuffers actions)
    {
        bool doJump = actions.DiscreteActions[0] == 1;

        if (doJump) {
            flappy.Jump();
        }
    }

    // Heuristic() substitui o modelo por controle manual, usado para testar o ambiente e para gravar
    // demonstrações (Behavior Type = Heuristic Only no Behavior Parameters). Sem modelo nem treinador
    // Python, é este método que decide a ação a cada decisão.
    public override void Heuristic(in ActionBuffers actionsOut)
    {
        ActionSegment<int> discreteActions = actionsOut.DiscreteActions;

        // Default action: no jump (0)
        discreteActions[0] = 0;

        // Check for manual input to trigger a jump (set to 1)
        // Tecla usada para bater asas manualmente: barra de espaço.
        if (Keyboard.current.spaceKey.IsPressed())
        {
            discreteActions[0] = 1;
        }
    }

    // Função auxiliar, não faz parte do ciclo de vida do Agent: procura, entre os objetos com a tag
    // "Pipeblank", o mais próximo à frente do pássaro no eixo X. Usada por CollectObservations acima.
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
