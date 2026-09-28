using System.Globalization;
using System.IO;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

/// <summary>
/// In-game training panel for the tutorial: trainer status, steps, episodes, score, rewards, a
/// time-scale slider and a sound switch. It installs itself after the first scene loads, survives the
/// scene reload that follows every FlappyBird death, and only reads agent and Academy state.
/// </summary>
public class TrainingHud : MonoBehaviour
{
    // Layout is authored for a 1080-pixel-tall screen at UI scale 1; GUI.matrix scales it to the real
    // screen height times the user's UI scale.
    const float ReferenceHeight = 1080f;
    const float PanelX = 16f;
    const float PanelY = 16f;
    const float PanelWidth = 340f;
    const float Padding = 12f;
    const float TitleHeight = 30f;
    const float SizeButtonWidth = 36f;
    const float SizeButtonHeight = 26f;
    const float RowHeight = 26f;
    const float ValueWidth = 80f;
    const float SoundButtonWidth = 170f;
    const float Gap = 6f;
    const float ChartHeight = 90f;
    const float SliderHeight = 20f;
    const float ButtonHeight = 30f;
    const float FooterHeight = 22f;
    const float TooltipWidth = 260f;
    const float ModelLabelWidth = 80f;
    const float ResultsLabelWidth = 60f;
    const float VersionWidth = 60f;

    const float DefaultUiScale = 1.6f;
    const float MinUiScale = 1f;
    const float MaxUiScale = 2.5f;
    const float UiScaleStep = 0.2f;
    const string UiScaleKey = "TrainingHud.Scale";
    const string SoundKey = "TrainingHud.Sound";

    // Smaller windows (the trainer asks for 84x84 by default) are reopened at the build's default size.
    const int MinWindowWidth = 640;
    const int MinWindowHeight = 360;
    const int WindowWidth = 1024;
    const int WindowHeight = 576;
    const float WindowRecheckInterval = 0.5f;
    const float WindowRecheckPeriod = 15f;

    const int ChartSize = 50;
    const int MeanSize = 20;
    const float MinTimeScale = 1f;
    const float MaxTimeScale = 20f;
    const float RefreshInterval = 0.1f;
    const float SearchInterval = 0.5f;
    const string SignedFormat = "+0.00;-0.00;0.00";
    const string NoData = "...";
    const string SoundTooltip = "Liga ou desliga os sons do jogo. Durante o treino, o som fica sempre desligado.";
    const float ResultsRefreshInterval = 2f;
    const string FooterHintText = "H esconde, M som, -/+ zoom";
    const string HiddenHintText = "H mostra o painel";
    const float HiddenHintDuration = 8f;
    const string TensorBoardUrl = "http://localhost:6006";

    static readonly Color PanelColor = new Color(0f, 0f, 0f, 0.7f);
    static readonly Color TooltipColor = new Color(0.05f, 0.05f, 0.05f, 0.95f);
    static readonly Color ChartColor = new Color(1f, 1f, 1f, 0.08f);
    static readonly Color ZeroLineColor = new Color(1f, 1f, 1f, 0.6f);
    static readonly Color PositiveColor = new Color(0.35f, 0.85f, 0.45f, 1f);
    static readonly Color NegativeColor = new Color(0.95f, 0.4f, 0.35f, 1f);
    static readonly Color InferenceColor = new Color(1f, 0.75f, 0.2f, 1f);

    public static TrainingHud Instance { get; private set; }

    public int EpisodesSeen { get; private set; }
    public float LastEpisodeReward { get; private set; }
    // Zero until the first episode ends.
    public float MeanLast20 { get; private set; }
    public bool Visible { get; private set; } = true;
    // User multiplier on top of the screen-height scaling, saved in PlayerPrefs.
    public float UiScale { get; private set; } = DefaultUiScale;
    // Sound preference, saved in PlayerPrefs; off unless the user turns it on.
    public bool SoundOn { get; private set; }

    /// <summary>True while the mouse is over the visible panel, so the game can ignore clicks meant for it.</summary>
    public static bool PointerOverPanel
    {
        get
        {
            TrainingHud hud = Instance;
            Mouse mouse = Mouse.current;
            if (hud == null || !hud.Visible || hud.headless || mouse == null)
                return false;
            // Mouse positions start at the bottom left, GUI rectangles at the top left.
            Vector2 position = mouse.position.ReadValue();
            return hud.panelScreenRect.Contains(new Vector2(position.x, Screen.height - position.y));
        }
    }

    readonly GUIContent smallerLabel = new GUIContent("A-", "Diminui o painel");
    readonly GUIContent largerLabel = new GUIContent("A+", "Aumenta o painel");
    readonly GUIContent connectedLabel = new GUIContent("Treinador conectado",
        "O mlagents-learn está conectado e decide as ações do agente. Se estiver treinando, cada decisão também ajuda o agente a aprender.");
    readonly GUIContent inferenceLabel = new GUIContent("Inferência (sem treinador)",
        "Nenhum treinador conectado. O agente só usa o modelo que já foi treinado e não aprende nada novo.");
    readonly GUIContent decisionStepsLabel = new GUIContent("Passos",
        "Decisões tomadas pelo agente desta janela desde que o jogo abriu. Com um só ambiente e sem --resume, é o mesmo número que o treinador mostra como Step.");
    readonly GUIContent simulationStepsLabel = new GUIContent("Passos",
        "Passos da simulação desde que o jogo abriu.");
    readonly GUIContent episodesLabel = new GUIContent("Episódios",
        "Episódios que já terminaram desde que o jogo abriu. Um episódio acaba quando o agente morre, alcança o objetivo ou atinge o limite de passos.");
    readonly GUIContent scoreLabel = new GUIContent("Pontuação",
        "Canos que o pássaro ultrapassou nesta vida. É o mesmo placar que aparece no jogo.");
    readonly GUIContent bestScoreLabel = new GUIContent("Melhor pontuação",
        "A maior pontuação de uma vida desde que o jogo abriu.");
    readonly GUIContent modelLabel = new GUIContent("Modelo",
        "Arquivo .onnx que escolhe as ações quando não há treinador. Com o treinador conectado, as ações vêm do Python.");
    readonly GUIContent rewardLabel = new GUIContent("Recompensa do episódio",
        "Soma das recompensas deste episódio até agora. É esse número que o treino tenta aumentar.");
    readonly GUIContent meanLabel = new GUIContent("Média (últimos 20)",
        "Média da recompensa final dos últimos 20 episódios. Num treino, se ela sobe com o tempo, o agente está aprendendo.");
    readonly GUIContent tensorBoardLabel = new GUIContent("Recompensas: veja o TensorBoard",
        "Este agente encerra os próprios episódios, então o painel não vê a recompensa final de cada um. As curvas de recompensa estão no TensorBoard.");
    readonly GUIContent chartLabel = new GUIContent("Últimos 50 episódios",
        "Cada barra é a recompensa final de um episódio, do mais antigo (esquerda) ao mais novo (direita). Para cima é positiva, para baixo é negativa.");
    readonly GUIContent speedLabel = new GUIContent("Velocidade",
        "20x é o padrão do treino. Em 1x fica fácil acompanhar o pássaro, mas o treino avança bem mais devagar.");
    readonly GUIContent speed1Label = new GUIContent("1x", "A menor velocidade, boa para assistir. Sem treinador, é o tempo real.");
    readonly GUIContent speed5Label = new GUIContent("5x", "Cinco vezes a velocidade de 1x.");
    readonly GUIContent speed20Label = new GUIContent("20x", "Velocidade padrão do treino.");
    readonly GUIContent soundLabel = new GUIContent("Som", SoundTooltip);
    readonly GUIContent soundOffLabel = new GUIContent("desligado", SoundTooltip);
    readonly GUIContent soundOnLabel = new GUIContent("ligado", SoundTooltip);
    readonly GUIContent soundTrainingLabel = new GUIContent("desligado (treino)", SoundTooltip);
    readonly GUIContent resultsFolderLabel = new GUIContent("Pasta",
        "Com o treinador conectado, é a pasta desta execução. Sem treinador, é a execução mais recente dentro de results.");
    readonly GUIContent resultsCheckpointLabel = new GUIContent("Salvo",
        "O arquivo .onnx mais recente nesta pasta. O treinador grava um a cada checkpoint_interval passos, valor definido no .yaml."
        + " No fim de um treino, mesmo interrompido com Ctrl+C, grava também o modelo final.");
    readonly GUIContent tensorBoardButtonLabel = new GUIContent("TensorBoard",
        "Abre " + TensorBoardUrl + " no navegador. Antes, rode tensorboard --logdir results em outro terminal, na raiz do repositório.");
    // Text set in Awake: Application.version is unsafe to read from a field initializer.
    readonly GUIContent versionLabel = new GUIContent();
    readonly GUIContent hiddenHintLabel = new GUIContent(HiddenHintText);
    readonly GUIContent tooltipContent = new GUIContent();
    // Mutable value cells, updated only when their cached, ellipsized text changes (see CachedEllipsis).
    readonly GUIContent modelValueContent = new GUIContent();
    readonly GUIContent resultsFolderValueContent = new GUIContent();
    readonly GUIContent resultsCheckpointValueContent = new GUIContent();
    readonly GUIContent footerHintContent = new GUIContent();

    readonly CachedText stepsText = new CachedText("N0");
    readonly CachedText episodesText = new CachedText("N0");
    readonly CachedText scoreText = new CachedText("0");
    readonly CachedText bestScoreText = new CachedText("0");
    readonly CachedText rewardText = new CachedText(SignedFormat);
    readonly CachedText meanText = new CachedText(SignedFormat);
    readonly CachedText speedText = new CachedText("0.#'x'");

    // Ellipsized on demand from OnGUI, since measuring text needs a GUIStyle.
    readonly CachedEllipsis modelValueCache = new CachedEllipsis();
    readonly CachedEllipsis resultsFolderCache = new CachedEllipsis();
    readonly CachedEllipsis resultsCheckpointCache = new CachedEllipsis();
    readonly CachedEllipsis footerHintCache = new CachedEllipsis();

    // Ring buffer with the final reward of the last ChartSize episodes.
    readonly float[] rewards = new float[ChartSize];
    int rewardCount;
    int rewardHead;
    float chartRange = 1f;

    Agent agent;
    bool tracking;
    bool searchPending = true;
    float nextSearch;
    int completedEpisodes;
    int lastAgentStep;
    float currentReward;
    // 0 when the agent has no DecisionRequester.
    int decisionPeriod;
    int lastTotalSteps;
    // Set once the tracked agent ends its own episodes, whose final reward the panel cannot see.
    bool rewardsUnknown;

    // Refreshed together with decisionPeriod whenever TrackAgent finds a (new) agent.
    bool hasModel;
    string modelName = "";
    string modelDisplayRaw = "";
    BehaviorType behaviorType = BehaviorType.Default;

    bool hasScore;
    int score;
    int bestScore;

    bool academyReady;
    // Next window recheck in real time, 0 once the recheck period is over.
    float windowRecheckAt;
    float windowRecheckEnd;
    // Set by a resize and cleared once the window is large again, so each small window is resized once.
    bool windowResizeRequested;
    bool headless;
    bool connected;
    float nextRefresh;
    // Real time the panel was last hidden; DrawHiddenHint stops drawing HiddenHintDuration after this.
    float hiddenAt;

    // Results folder scan: throttled separately because it touches disk, unlike the other cached text.
    float nextResultsRefresh;
    bool hasResultsFolder;
    string resultsFolderRaw = "";
    string resultsFolderFullPath = "";
    string resultsCheckpointRaw = "";
    string resultsCheckpointTooltip = "";
    bool loggedResultsError;

    Rect panelScreenRect;
    // Cached from the last OnGUI call: true when a larger UiScale would not grow the rendered panel (either
    // the window height is already the limit, or UiScale is at MaxUiScale). Read by the "=" key in Update.
    bool uiScaleAtCeiling;
    NumberFormatInfo numberFormat;
    Texture2D whiteTexture;
    GUIStyle labelStyle;
    GUIStyle valueStyle;
    GUIStyle titleStyle;
    GUIStyle footerStyle;
    GUIStyle tooltipStyle;
    GUIStyle buttonStyle;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Install()
    {
        if (Instance != null)
            return;
        var host = new GameObject("TrainingHud");
        DontDestroyOnLoad(host);
        host.AddComponent<TrainingHud>();
    }

    /// <summary>Shows or hides the panel, like the H key.</summary>
    public void ToggleVisible()
    {
        Visible = !Visible;
        if (!Visible)
            hiddenAt = Time.realtimeSinceStartup;
        nextRefresh = 0f;
    }

    /// <summary>Sets Time.timeScale, clamped to the slider range (1 to 20).</summary>
    public void SetTimeScale(float value)
    {
        if (float.IsNaN(value))
            return;
        float clamped = Mathf.Clamp(value, MinTimeScale, MaxTimeScale);
        if (Time.timeScale != clamped)
            Time.timeScale = clamped;
        nextRefresh = 0f;
    }

    /// <summary>Sets the panel size multiplier (1 to 2.5) and remembers it across runs.</summary>
    public void SetUiScale(float value)
    {
        if (float.IsNaN(value))
            return;
        // Rounding keeps repeated 0.2 steps from drifting (1.6 + 0.2 = 1.8000001).
        float clamped = Mathf.Round(Mathf.Clamp(value, MinUiScale, MaxUiScale) * 100f) / 100f;
        if (clamped == UiScale)
            return;
        UiScale = clamped;
        PlayerPrefs.SetFloat(UiScaleKey, UiScale);
        PlayerPrefs.Save();
    }

    /// <summary>Turns the game sound on or off and remembers it. Ignored while a trainer is connected.</summary>
    public void SetSound(bool on)
    {
        if (Academy.IsInitialized && Academy.Instance.IsCommunicatorOn)
            return;
        SoundOn = on;
        PlayerPrefs.SetInt(SoundKey, on ? 1 : 0);
        PlayerPrefs.Save();
        if (academyReady)
            AudioListener.volume = on ? 1f : 0f;
    }

    void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(this);
            return;
        }
        Instance = this;
        useGUILayout = false;
        headless = SystemInfo.graphicsDeviceType == GraphicsDeviceType.Null;
        // Application.version is unsafe to read from a field initializer, so it is set here instead.
        versionLabel.text = "v" + Application.version;

        // OnGUI never draws without a graphics device, so the texture is only needed with one.
        if (!headless)
        {
            whiteTexture = new Texture2D(1, 1) { hideFlags = HideFlags.HideAndDontSave };
            whiteTexture.SetPixel(0, 0, Color.white);
            whiteTexture.Apply();
        }

        // PT-BR number style: 12.345 and -1,50.
        numberFormat = (NumberFormatInfo)CultureInfo.InvariantCulture.NumberFormat.Clone();
        numberFormat.NumberDecimalSeparator = ",";
        numberFormat.NumberGroupSeparator = ".";

        UiScale = Mathf.Clamp(PlayerPrefs.GetFloat(UiScaleKey, DefaultUiScale), MinUiScale, MaxUiScale);
        SoundOn = PlayerPrefs.GetInt(SoundKey, 0) == 1;

        // The first scene finished loading before this object existed.
        hasScore = FindAnyObjectByType<ScoreManagerScript>() != null;
        OnAcademyReady();
    }

    void OnEnable()
    {
        SceneManager.sceneLoaded += OnSceneLoaded;
    }

    void OnDisable()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
    }

    void OnDestroy()
    {
        if (Instance == this)
            Instance = null;
        if (whiteTexture != null)
            Destroy(whiteTexture);
    }

    void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        searchPending = true;
        hasScore = FindAnyObjectByType<ScoreManagerScript>() != null;
    }

    void Update()
    {
        Keyboard keyboard = Keyboard.current;
        if (keyboard != null)
        {
            if (keyboard.hKey.wasPressedThisFrame)
                ToggleVisible();
            if (keyboard.mKey.wasPressedThisFrame)
                SetSound(!SoundOn);
            if (keyboard.minusKey.wasPressedThisFrame || keyboard.numpadMinusKey.wasPressedThisFrame)
                SetUiScale(UiScale - UiScaleStep);
            if ((keyboard.equalsKey.wasPressedThisFrame || keyboard.numpadPlusKey.wasPressedThisFrame) && Visible && !uiScaleAtCeiling)
                SetUiScale(UiScale + UiScaleStep);
        }

        if (!academyReady)
        {
            OnAcademyReady();
        }
        else if (windowRecheckAt > 0f && Time.realtimeSinceStartup >= windowRecheckAt)
        {
            float now = Time.realtimeSinceStartup;
            windowRecheckAt = now < windowRecheckEnd ? now + WindowRecheckInterval : 0f;
            CheckWindow();
        }
        // Academy.Instance would create an Academy if none exists, so check first.
        if (Academy.IsInitialized)
            lastTotalSteps = Academy.Instance.TotalStepCount;

        TrackAgent();

        if (hasScore)
        {
            score = ScoreManagerScript.Score;
            bestScore = Mathf.Max(bestScore, score);
        }

        // Real time, because Time.time follows the time scale and the trainer's capture frame rate.
        if (Visible && !headless && Time.realtimeSinceStartup >= nextRefresh)
        {
            nextRefresh = Time.realtimeSinceStartup + RefreshInterval;
            RefreshTexts();
        }
        // Slower and separate from RefreshTexts because this one touches disk.
        if (Visible && !headless && Time.realtimeSinceStartup >= nextResultsRefresh)
        {
            nextResultsRefresh = Time.realtimeSinceStartup + ResultsRefreshInterval;
            RefreshResultsInfo();
        }
    }

    // Runs once, as soon as the Academy exists. Academy.IsInitialized turns true only after the trainer
    // handshake, which also applies the trainer's engine settings (time scale, window size), so
    // IsCommunicatorOn is final here.
    void OnAcademyReady()
    {
        if (!Academy.IsInitialized)
            return;
        academyReady = true;
        Debug.Log("TrainingHud: ready (trainer " + Academy.Instance.IsCommunicatorOn + ", headless " + headless + ")");
        DecideSound();
        // Headless runs have no window, and the editor's Game view ignores Screen.SetResolution.
        if (headless || Application.isEditor)
            return;
        Debug.Log("TrainingHud: window " + Screen.width + "x" + Screen.height);
        CheckWindow();
        float now = Time.realtimeSinceStartup;
        windowRecheckEnd = now + WindowRecheckPeriod;
        windowRecheckAt = now + WindowRecheckInterval;
    }

    // Applies the saved sound preference without a trainer only. Under a trainer the volume is left to
    // the guard in FlappyScript.Start().
    void DecideSound()
    {
        if (Academy.Instance.IsCommunicatorOn)
            return;
        AudioListener.volume = SoundOn ? 1f : 0f;
        string state = SoundOn ? "on" : PlayerPrefs.HasKey(SoundKey) ? "off (saved choice)" : "off by default";
        Debug.Log("TrainingHud: sound " + state);
    }

    // The trainer's size request lands during the handshake, but Screen.SetResolution only takes effect at
    // the end of a frame, and a slow first frame can delay it further; hence the rechecks.
    void CheckWindow()
    {
        int width = Screen.width;
        int height = Screen.height;
        if (width >= MinWindowWidth && height >= MinWindowHeight)
        {
            windowResizeRequested = false;
            return;
        }
        // A resize that has not taken effect yet (or was refused) is not requested again.
        if (windowResizeRequested)
            return;
        windowResizeRequested = true;
        Screen.SetResolution(WindowWidth, WindowHeight, FullScreenMode.Windowed);
        Debug.Log("TrainingHud: window " + width + "x" + height + ", set to " + WindowWidth + "x" + WindowHeight);
    }

    void OnApplicationQuit()
    {
        if (academyReady)
            Debug.Log("TrainingHud: Passos " + ShownSteps() + " at quit (" + lastTotalSteps + " simulation steps, decision period " + decisionPeriod + ")");
    }

    // The trainer's Step counts decisions, the Academy counts simulation steps.
    int ShownSteps()
    {
        return decisionPeriod > 0 ? lastTotalSteps / decisionPeriod : lastTotalSteps;
    }

    void TrackAgent()
    {
        if (agent == null)
        {
            if (tracking)
            {
                // The agent was destroyed, as on the scene reload after each FlappyBird death.
                RecordEpisodeEnd(1);
                tracking = false;
            }

            float now = Time.realtimeSinceStartup;
            if (!searchPending && now < nextSearch)
                return;
            searchPending = false;
            nextSearch = now + SearchInterval;

            agent = FindAnyObjectByType<Agent>();
            if (agent == null)
                return;
            tracking = true;
            completedEpisodes = agent.CompletedEpisodes;
            lastAgentStep = agent.StepCount;
            var requester = agent.GetComponent<DecisionRequester>();
            decisionPeriod = requester != null ? Mathf.Max(1, requester.DecisionPeriod) : 0;

            var behaviorParameters = agent.GetComponent<BehaviorParameters>();
            UnityEngine.Object model = behaviorParameters != null ? behaviorParameters.Model : null;
            hasModel = model != null;
            modelName = hasModel ? model.name : "";
            behaviorType = behaviorParameters != null ? behaviorParameters.BehaviorType : BehaviorType.Default;
        }

        int completed = agent.CompletedEpisodes;
        if (completed > completedEpisodes)
        {
            // A living agent finished an episode, and its reward is already reset. Within one frame of
            // MaxStep that is the step limit, and the last frame's sample stands in for the final reward.
            // Anywhere else the agent called EndEpisode in the same step that gave the final reward.
            int stepsPerFrame = Mathf.CeilToInt(Time.maximumDeltaTime / Time.fixedDeltaTime) + 1;
            if (agent.MaxStep <= 0 || lastAgentStep + stepsPerFrame < agent.MaxStep)
                rewardsUnknown = true;
            RecordEpisodeEnd(completed - completedEpisodes);
            completedEpisodes = completed;
        }
        currentReward = agent.GetCumulativeReward();
        lastAgentStep = agent.StepCount;
    }

    void RecordEpisodeEnd(int episodes)
    {
        EpisodesSeen += episodes;
        LastEpisodeReward = currentReward;
        rewards[rewardHead] = currentReward;
        rewardHead = (rewardHead + 1) % ChartSize;
        rewardCount = Mathf.Min(rewardCount + 1, ChartSize);

        int meanCount = Mathf.Min(rewardCount, MeanSize);
        float sum = 0f;
        for (int i = 1; i <= meanCount; i++)
            sum += rewards[(rewardHead - i + ChartSize) % ChartSize];
        MeanLast20 = sum / meanCount;

        float largest = 0f;
        for (int i = 0; i < rewardCount; i++)
            largest = Mathf.Max(largest, Mathf.Abs(rewards[i]));
        chartRange = Mathf.Max(largest, 0.01f);

        currentReward = 0f;
    }

    // Finds the current run folder and its newest checkpoint. Prefers the folder mlagents-learn itself is
    // writing to (from this process's own log path), which is correct even with --results-dir; otherwise
    // falls back to the newest subfolder of <cwd>/results. Read-only, and every exception is caught so a
    // permissions or IO problem just hides the rows instead of throwing.
    void RefreshResultsInfo()
    {
        try
        {
            bool trainerConnected = Academy.IsInitialized && Academy.Instance.IsCommunicatorOn;
            string runFolder = trainerConnected ? RunFolderFromLogPath() : null;
            bool viaLogPath = runFolder != null;

            if (!viaLogPath)
            {
                string resultsRoot = Path.Combine(Directory.GetCurrentDirectory(), "results");
                if (!Directory.Exists(resultsRoot))
                {
                    hasResultsFolder = false;
                    return;
                }
                runFolder = NewestSubfolder(resultsRoot);
                if (runFolder == null)
                {
                    // results exists but no run has written a folder into it yet; a transient startup window.
                    hasResultsFolder = true;
                    resultsFolderFullPath = resultsRoot;
                    resultsFolderRaw = "nenhuma execução ainda";
                    resultsCheckpointRaw = "nada salvo ainda";
                    resultsCheckpointTooltip = "O treinador ainda não criou uma pasta de execução em " + resultsRoot + ".";
                    loggedResultsError = false;
                    return;
                }
            }

            hasResultsFolder = true;
            resultsFolderFullPath = runFolder;
            // Shown with forward slashes on every OS; only this display string changes, never a path used for IO.
            resultsFolderRaw = (viaLogPath
                ? Path.Combine(Path.GetFileName(Path.GetDirectoryName(runFolder)), Path.GetFileName(runFolder))
                : Path.Combine("results", Path.GetFileName(runFolder))).Replace('\\', '/');

            string checkpoint = NewestOnnxFile(runFolder, out System.DateTime checkpointTime);
            if (checkpoint == null)
            {
                resultsCheckpointRaw = "nada salvo ainda";
                resultsCheckpointTooltip = "";
            }
            else
            {
                var age = System.DateTime.UtcNow - checkpointTime;
                resultsCheckpointRaw = FormatCheckpointValue(checkpoint, age, numberFormat);
                resultsCheckpointTooltip = checkpoint;
            }
            loggedResultsError = false;
        }
        catch (System.Exception e)
        {
            hasResultsFolder = false;
            if (!loggedResultsError)
            {
                loggedResultsError = true;
                Debug.Log("TrainingHud: results info hidden after a file system error (" + e.GetType().Name + ")");
            }
        }
    }

    // The run folder mlagents-learn is writing to, parsed from this process's own log file path
    // (-logFile <run-folder>/run_logs/Player-N.log). Trusted regardless of where it sits, since
    // --results-dir can point it outside <cwd>/results. Null when the shape does not match.
    string RunFolderFromLogPath()
    {
        string logPath = Application.consoleLogPath;
        if (string.IsNullOrEmpty(logPath))
            return null;
        string runLogsDir = Path.GetDirectoryName(logPath);
        if (string.IsNullOrEmpty(runLogsDir) || Path.GetFileName(runLogsDir) != "run_logs")
            return null;
        string runDir = Path.GetDirectoryName(runLogsDir);
        return string.IsNullOrEmpty(runDir) ? null : runDir;
    }

    // The subfolder of root whose own last-write time (set when a run starts and writes its first files
    // directly inside it) is newest. A cheap proxy for "which run was touched most recently."
    string NewestSubfolder(string root)
    {
        string newest = null;
        System.DateTime newestTime = System.DateTime.MinValue;
        foreach (string dir in Directory.GetDirectories(root))
        {
            System.DateTime time = Directory.GetLastWriteTimeUtc(dir);
            if (newest == null || time > newestTime)
            {
                newest = dir;
                newestTime = time;
            }
        }
        return newest;
    }

    // The most recently written .onnx anywhere under runFolder: a numbered checkpoint or the final model.
    // Returns its write time too, so the caller never has to stat the file again after it may be gone.
    string NewestOnnxFile(string runFolder, out System.DateTime time)
    {
        string newest = null;
        System.DateTime newestTime = System.DateTime.MinValue;
        foreach (string file in Directory.GetFiles(runFolder, "*.onnx", SearchOption.AllDirectories))
        {
            System.DateTime fileTime = File.GetLastWriteTimeUtc(file);
            if (newest == null || fileTime > newestTime)
            {
                newest = file;
                newestTime = fileTime;
            }
        }
        time = newestTime;
        return newest;
    }

    static string FormatAge(System.TimeSpan age)
    {
        // Truncated, not rounded, so this never reads "há 60 s" or "há 60 min".
        double seconds = System.Math.Max(0, age.TotalSeconds);
        if (seconds < 60)
            return "há " + (int)seconds + " s";
        if (seconds < 3600)
            return "há " + (int)(seconds / 60) + " min";
        return "há " + (int)(seconds / 3600) + " h";
    }

    // Age first, since it is what matters and must never be the part an ellipsis cuts; the step number (or
    // "modelo final" when the file has none, e.g. the run's final <Behavior>.onnx) comes after in parens.
    static string FormatCheckpointValue(string checkpointPath, System.TimeSpan age, NumberFormatInfo numberFormat)
    {
        string ageText = FormatAge(age);
        string name = Path.GetFileNameWithoutExtension(checkpointPath);
        int dash = name.LastIndexOf('-');
        if (dash >= 0 && dash < name.Length - 1 && long.TryParse(name.Substring(dash + 1), out long steps))
            return ageText + " (passo " + steps.ToString("N0", numberFormat) + ")";
        return ageText + " (modelo final)";
    }

    void RefreshTexts()
    {
        connected = Academy.IsInitialized && Academy.Instance.IsCommunicatorOn;
        stepsText.Set(ShownSteps(), numberFormat);
        episodesText.Set(EpisodesSeen, numberFormat);
        scoreText.Set(score, numberFormat);
        bestScoreText.Set(bestScore, numberFormat);
        rewardText.Set(currentReward, numberFormat);
        meanText.Set(MeanLast20, numberFormat);
        speedText.Set(Time.timeScale, numberFormat);
        modelDisplayRaw = ComputeModelDisplay();
    }

    // HeuristicOnly and InferenceOnly override the trainer/model default, matching ml-agents itself: a
    // heuristic-only agent never takes actions from a model or trainer, and an inference-only one never
    // takes them from a trainer even when one is connected.
    string ComputeModelDisplay()
    {
        if (behaviorType == BehaviorType.HeuristicOnly)
            return "nenhum (controle manual)";
        if (behaviorType == BehaviorType.InferenceOnly)
            return hasModel ? modelName : "nenhum (controle manual)";
        return connected ? "controlado pelo treinador" : hasModel ? modelName : "nenhum (controle manual)";
    }

    // Height of the panel in layout units; must match the rows drawn in OnGUI.
    float PanelHeight()
    {
        int statRows = 2 + (hasScore ? 2 : 0) + 1 + (rewardsUnknown ? 1 : 2);
        float chart = rewardsUnknown ? 0f : RowHeight + ChartHeight + Gap;
        float resultsHeight = hasResultsFolder ? 2f * RowHeight + Gap : 0f;
        return 2f * Padding + TitleHeight + RowHeight + Gap + statRows * RowHeight + Gap + chart
            + RowHeight + SliderHeight + Gap + ButtonHeight + Gap + ButtonHeight + Gap + resultsHeight + ButtonHeight + Gap + FooterHeight;
    }

    void OnGUI()
    {
        if (headless)
            return;
        if (!Visible)
        {
            if (Time.realtimeSinceStartup - hiddenAt < HiddenHintDuration)
                DrawHiddenHint();
            return;
        }

        // Controls set GUI.tooltip while they are hovered in this Repaint pass, and DrawTooltip reads it at
        // the end of the same pass; clear the previous pass's value first so it cannot stick.
        if (Event.current.type == EventType.Repaint)
            GUI.tooltip = "";

        EnsureStyles();
        Matrix4x4 previousMatrix = GUI.matrix;
        Color previousColor = GUI.color;
        float panelHeight = PanelHeight();
        float screenHeight = Mathf.Max(Screen.height, 1);
        // The user's multiplier never lets the panel grow past the screen height.
        float uiScaleTerm = screenHeight / ReferenceHeight * UiScale;
        float windowFitTerm = screenHeight / (panelHeight + 2f * PanelY);
        float scale = Mathf.Min(uiScaleTerm, windowFitTerm);
        // A+ (and "=") are disabled once one more step would grow the rendered panel by less than half a step.
        uiScaleAtCeiling = UiScale >= MaxUiScale
            || windowFitTerm < screenHeight / ReferenceHeight * (UiScale + 0.5f * UiScaleStep);
        GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
        panelScreenRect = new Rect(PanelX * scale, PanelY * scale, PanelWidth * scale, panelHeight * scale);

        float x = PanelX + Padding;
        float width = PanelWidth - 2f * Padding;
        float y = PanelY + Padding;
        Fill(new Rect(PanelX, PanelY, PanelWidth, panelHeight), PanelColor);

        float sizeButtonsX = x + width - 2f * SizeButtonWidth - Gap;
        GUI.Label(new Rect(x, y, sizeButtonsX - x - Gap, TitleHeight), "Painel de treino", titleStyle);
        float sizeButtonY = y + (TitleHeight - SizeButtonHeight) * 0.5f;
        if (GUI.Button(new Rect(sizeButtonsX, sizeButtonY, SizeButtonWidth, SizeButtonHeight), smallerLabel, buttonStyle))
            SetUiScale(UiScale - UiScaleStep);
        bool largerWasEnabled = GUI.enabled;
        GUI.enabled = largerWasEnabled && !uiScaleAtCeiling;
        if (GUI.Button(new Rect(sizeButtonsX + SizeButtonWidth + Gap, sizeButtonY, SizeButtonWidth, SizeButtonHeight), largerLabel, buttonStyle))
            SetUiScale(UiScale + UiScaleStep);
        GUI.enabled = largerWasEnabled;
        y += TitleHeight;

        Fill(new Rect(x, y + (RowHeight - 10f) * 0.5f, 10f, 10f), connected ? PositiveColor : InferenceColor);
        GUI.Label(new Rect(x + 16f, y, width - 16f, RowHeight), connected ? connectedLabel : inferenceLabel, labelStyle);
        y += RowHeight + Gap;

        y = DrawRow(x, y, width, decisionPeriod > 0 ? decisionStepsLabel : simulationStepsLabel, stepsText.Text);
        y = DrawRow(x, y, width, episodesLabel, episodesText.Text);
        if (hasScore)
        {
            y = DrawRow(x, y, width, scoreLabel, scoreText.Text);
            y = DrawRow(x, y, width, bestScoreLabel, bestScoreText.Text);
        }
        y = DrawModelRow(x, y, width);
        if (rewardsUnknown)
        {
            GUI.Label(new Rect(x, y, width, RowHeight), tensorBoardLabel, labelStyle);
            y += RowHeight + Gap;
        }
        else
        {
            y = DrawRow(x, y, width, rewardLabel, tracking ? rewardText.Text : NoData);
            y = DrawRow(x, y, width, meanLabel, rewardCount > 0 ? meanText.Text : NoData);
            y += Gap;
            GUI.Label(new Rect(x, y, width, RowHeight), chartLabel, labelStyle);
            y += RowHeight;
            DrawChart(new Rect(x, y, width, ChartHeight));
            y += ChartHeight + Gap;
        }

        y = DrawRow(x, y, width, speedLabel, speedText.Text);
        // GUI.changed is only set by user input, so the trainer's time scale is never overwritten on its own.
        GUI.changed = false;
        float picked = GUI.HorizontalSlider(new Rect(x, y, width, SliderHeight), Time.timeScale, MinTimeScale, MaxTimeScale);
        if (GUI.changed)
            SetTimeScale(Mathf.Round(picked));
        y += SliderHeight + Gap;

        float buttonWidth = (width - 2f * Gap) / 3f;
        if (GUI.Button(new Rect(x, y, buttonWidth, ButtonHeight), speed1Label, buttonStyle))
            SetTimeScale(1f);
        if (GUI.Button(new Rect(x + buttonWidth + Gap, y, buttonWidth, ButtonHeight), speed5Label, buttonStyle))
            SetTimeScale(5f);
        if (GUI.Button(new Rect(x + 2f * (buttonWidth + Gap), y, buttonWidth, ButtonHeight), speed20Label, buttonStyle))
            SetTimeScale(20f);
        y += ButtonHeight + Gap;

        GUI.Label(new Rect(x, y, width - SoundButtonWidth, ButtonHeight), soundLabel, labelStyle);
        bool wasEnabled = GUI.enabled;
        GUI.enabled = !connected;
        GUIContent soundState = connected ? soundTrainingLabel : SoundOn ? soundOnLabel : soundOffLabel;
        if (GUI.Button(new Rect(x + width - SoundButtonWidth, y, SoundButtonWidth, ButtonHeight), soundState, buttonStyle))
            SetSound(!SoundOn);
        GUI.enabled = wasEnabled;
        y += ButtonHeight + Gap;

        if (hasResultsFolder)
        {
            y = DrawResultsRows(x, y, width);
            y += Gap;
        }
        if (GUI.Button(new Rect(x, y, width, ButtonHeight), tensorBoardButtonLabel, buttonStyle))
        {
            Application.OpenURL(TensorBoardUrl);
            Debug.Log("TrainingHud: opening " + TensorBoardUrl);
        }
        y += ButtonHeight + Gap;

        float hintWidth = width - VersionWidth;
        if (footerHintCache.Set(FooterHintText, footerStyle, hintWidth))
            footerHintContent.text = footerHintCache.Text;
        GUI.Label(new Rect(x, y, hintWidth, FooterHeight), footerHintContent, footerStyle);
        GUI.Label(new Rect(x + hintWidth, y, VersionWidth, FooterHeight), versionLabel, footerStyle);

        DrawTooltip(scale);
        GUI.matrix = previousMatrix;
        GUI.color = previousColor;
    }

    float DrawRow(float x, float y, float width, GUIContent label, string value)
    {
        GUI.Label(new Rect(x, y, width - ValueWidth, RowHeight), label, labelStyle);
        GUI.Label(new Rect(x + width - ValueWidth, y, ValueWidth, RowHeight), value, valueStyle);
        return y + RowHeight;
    }

    // Wider value column than DrawRow's, since the model name or trainer state does not fit in ValueWidth.
    float DrawModelRow(float x, float y, float width)
    {
        float valueWidth = width - ModelLabelWidth;
        GUI.Label(new Rect(x, y, ModelLabelWidth, RowHeight), modelLabel, labelStyle);
        if (modelValueCache.Set(modelDisplayRaw, valueStyle, valueWidth))
        {
            modelValueContent.text = modelValueCache.Text;
            modelValueContent.tooltip = modelValueCache.WasTruncated ? modelDisplayRaw : "";
        }
        GUI.Label(new Rect(x + ModelLabelWidth, y, valueWidth, RowHeight), modelValueContent, valueStyle);
        return y + RowHeight;
    }

    // The current run's folder and its newest checkpoint, same two-column layout as DrawModelRow. Called
    // only while hasResultsFolder.
    float DrawResultsRows(float x, float y, float width)
    {
        float valueWidth = width - ResultsLabelWidth;

        GUI.Label(new Rect(x, y, ResultsLabelWidth, RowHeight), resultsFolderLabel, labelStyle);
        if (resultsFolderCache.Set(resultsFolderRaw, valueStyle, valueWidth))
        {
            resultsFolderValueContent.text = resultsFolderCache.Text;
            resultsFolderValueContent.tooltip = resultsFolderFullPath;
        }
        GUI.Label(new Rect(x + ResultsLabelWidth, y, valueWidth, RowHeight), resultsFolderValueContent, valueStyle);
        y += RowHeight;

        GUI.Label(new Rect(x, y, ResultsLabelWidth, RowHeight), resultsCheckpointLabel, labelStyle);
        if (resultsCheckpointCache.Set(resultsCheckpointRaw, valueStyle, valueWidth))
        {
            resultsCheckpointValueContent.text = resultsCheckpointCache.Text;
            resultsCheckpointValueContent.tooltip = resultsCheckpointTooltip;
        }
        GUI.Label(new Rect(x + ResultsLabelWidth, y, valueWidth, RowHeight), resultsCheckpointValueContent, valueStyle);
        return y + RowHeight;
    }

    void DrawChart(Rect area)
    {
        if (Event.current.type != EventType.Repaint)
            return;

        Fill(area, ChartColor);
        float middle = area.y + area.height * 0.5f;
        float halfHeight = area.height * 0.5f - 1f;
        float slot = area.width / ChartSize;
        for (int i = 0; i < rewardCount; i++)
        {
            // Oldest on the left, newest against the right edge.
            float reward = rewards[(rewardHead - rewardCount + i + ChartSize) % ChartSize];
            float barHeight = Mathf.Max(1f, Mathf.Abs(reward) / chartRange * halfHeight);
            float left = area.xMax - (rewardCount - i) * slot;
            Rect bar = reward >= 0f
                ? new Rect(left, middle - barHeight, slot - 1f, barHeight)
                : new Rect(left, middle, slot - 1f, barHeight);
            // A zero reward is neither green nor red; its 1 px mark sits on the zero line.
            Fill(bar, reward > 0f ? PositiveColor : reward < 0f ? NegativeColor : ZeroLineColor);
        }
        Fill(new Rect(area.x, middle - 1f, area.width, 2f), ZeroLineColor);
    }

    void DrawTooltip(float scale)
    {
        string tip = GUI.tooltip;
        if (string.IsNullOrEmpty(tip) || Event.current.type != EventType.Repaint)
            return;

        tooltipContent.text = tip;
        float height = tooltipStyle.CalcHeight(tooltipContent, TooltipWidth);
        Vector2 mouse = Event.current.mousePosition;
        float screenWidth = Screen.width / scale;
        float screenHeight = Screen.height / scale;
        float left = Mathf.Max(0f, Mathf.Min(mouse.x + 16f, screenWidth - TooltipWidth - 4f));
        float top = Mathf.Max(0f, Mathf.Min(mouse.y + 16f, screenHeight - height - 4f));
        var box = new Rect(left, top, TooltipWidth, height);
        Fill(box, TooltipColor);
        GUI.Label(box, tooltipContent, tooltipStyle);
    }

    // Only line drawn while the panel is hidden, so H is discoverable again. No tooltip: it says everything.
    void DrawHiddenHint()
    {
        EnsureStyles();
        Matrix4x4 previousMatrix = GUI.matrix;
        float scale = Mathf.Max(Screen.height, 1) / ReferenceHeight * UiScale;
        GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
        var rect = new Rect(PanelX, PanelY, 180f, FooterHeight);
        Fill(rect, PanelColor);
        var textRect = new Rect(PanelX + Padding, PanelY, 180f - Padding, FooterHeight);
        GUI.Label(textRect, hiddenHintLabel, footerStyle);
        GUI.matrix = previousMatrix;
    }

    void Fill(Rect area, Color color)
    {
        GUI.color = color;
        GUI.DrawTexture(area, whiteTexture);
        GUI.color = Color.white;
    }

    void EnsureStyles()
    {
        if (labelStyle != null)
            return;

        // GUI.skin is only available inside OnGUI. Sizes are pixels at 1080p and UI scale 1.
        labelStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = 18,
            alignment = TextAnchor.MiddleLeft,
            wordWrap = false,
            clipping = TextClipping.Overflow,
        };
        labelStyle.normal.textColor = Color.white;
        labelStyle.hover.textColor = Color.white;
        valueStyle = new GUIStyle(labelStyle) { alignment = TextAnchor.MiddleRight };
        titleStyle = new GUIStyle(labelStyle) { fontSize = 21, fontStyle = FontStyle.Bold };
        footerStyle = new GUIStyle(labelStyle) { fontSize = 16 };
        footerStyle.normal.textColor = new Color(1f, 1f, 1f, 0.75f);
        tooltipStyle = new GUIStyle(labelStyle)
        {
            fontSize = 16,
            alignment = TextAnchor.UpperLeft,
            wordWrap = true,
            padding = new RectOffset(8, 8, 6, 6),
        };
        buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 17 };
    }

    // Formats a number only when it changes, so the periodic refresh rarely allocates.
    sealed class CachedText
    {
        readonly string format;
        double value = double.NaN;

        public CachedText(string format)
        {
            this.format = format;
        }

        public string Text { get; private set; } = "";

        public void Set(double newValue, NumberFormatInfo numberFormat)
        {
            if (newValue == value)
                return;
            value = newValue;
            Text = newValue.ToString(format, numberFormat);
        }
    }

    // Ellipsizes text to fit maxWidth under a GUIStyle, recomputed only when the source string changes so
    // repeated Repaint passes do not remeasure or allocate. Set returns true exactly when Text changed, so
    // callers know when to copy it into their own displayed GUIContent. Measures with its own reusable
    // GUIContent, since GUIContent.Temp is internal to UnityEngine and not callable from user code.
    sealed class CachedEllipsis
    {
        readonly GUIContent measure = new GUIContent();
        string source = "";

        public string Text { get; private set; } = "";
        public bool WasTruncated { get; private set; }

        public bool Set(string newValue, GUIStyle style, float maxWidth)
        {
            newValue = newValue ?? "";
            if (newValue == source)
                return false;
            source = newValue;
            measure.text = newValue;
            if (newValue.Length == 0 || style.CalcSize(measure).x <= maxWidth)
            {
                Text = newValue;
                WasTruncated = false;
                return true;
            }
            int lo = 0, hi = newValue.Length;
            while (lo < hi)
            {
                int mid = (lo + hi + 1) / 2;
                measure.text = newValue.Substring(0, mid) + "…";
                if (style.CalcSize(measure).x <= maxWidth)
                    lo = mid;
                else
                    hi = mid - 1;
            }
            Text = (lo > 0 ? newValue.Substring(0, lo) : "") + "…";
            WasTruncated = true;
            return true;
        }
    }
}
