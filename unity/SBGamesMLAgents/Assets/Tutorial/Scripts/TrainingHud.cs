using System.Globalization;
using Unity.MLAgents;
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
    readonly GUIContent connectedLabel = new GUIContent("Treinador conectado (?)",
        "Um treinador está conectado e controla o agente.");
    readonly GUIContent inferenceLabel = new GUIContent("Inferência (sem treinador) (?)",
        "Nenhum treinador conectado. O agente só usa o modelo que já foi treinado e não aprende nada novo.");
    readonly GUIContent decisionStepsLabel = new GUIContent("Passos (?)",
        "Decisões tomadas pelo agente neste processo. Com um ambiente só, é o mesmo número que o treinador mostra como Step.");
    readonly GUIContent simulationStepsLabel = new GUIContent("Passos (?)",
        "Passos da simulação desde que o jogo abriu.");
    readonly GUIContent episodesLabel = new GUIContent("Episódios (?)",
        "Episódios que já terminaram desde que o jogo abriu. Um episódio acaba quando o agente morre, alcança o objetivo ou atinge o limite de passos.");
    readonly GUIContent scoreLabel = new GUIContent("Pontuação (?)",
        "Canos que o pássaro ultrapassou nesta vida. É o mesmo placar que aparece no jogo.");
    readonly GUIContent bestScoreLabel = new GUIContent("Melhor pontuação (?)",
        "A maior pontuação de uma vida desde que o jogo abriu.");
    readonly GUIContent rewardLabel = new GUIContent("Recompensa do episódio (?)",
        "Soma das recompensas deste episódio até agora. É esse número que o treino tenta aumentar.");
    readonly GUIContent meanLabel = new GUIContent("Média (últimos 20) (?)",
        "Média da recompensa final dos últimos 20 episódios. Se ela sobe com o tempo, o agente está aprendendo.");
    readonly GUIContent tensorBoardLabel = new GUIContent("Recompensas: veja o TensorBoard (?)",
        "Este agente encerra os próprios episódios, então o painel não vê a recompensa final de cada um. As curvas de recompensa estão no TensorBoard.");
    readonly GUIContent chartLabel = new GUIContent("Últimos 50 episódios (?)",
        "Cada barra é a recompensa final de um episódio, do mais antigo (esquerda) ao mais novo (direita). Para cima é positiva, para baixo é negativa.");
    readonly GUIContent speedLabel = new GUIContent("Velocidade (?)",
        "20x é o padrão do treino. Em 1x você vê o jogo em tempo real, mas o treino fica 20 vezes mais lento.");
    readonly GUIContent speed1Label = new GUIContent("1x", "Tempo real, bom para assistir.");
    readonly GUIContent speed5Label = new GUIContent("5x", "Cinco vezes mais rápido que o tempo real.");
    readonly GUIContent speed20Label = new GUIContent("20x", "Velocidade padrão do treino.");
    readonly GUIContent soundLabel = new GUIContent("Som (?)", SoundTooltip);
    readonly GUIContent soundOffLabel = new GUIContent("desligado", SoundTooltip);
    readonly GUIContent soundOnLabel = new GUIContent("ligado", SoundTooltip);
    readonly GUIContent soundTrainingLabel = new GUIContent("desligado (treino)", SoundTooltip);
    readonly GUIContent tooltipContent = new GUIContent();

    readonly CachedText stepsText = new CachedText("N0");
    readonly CachedText episodesText = new CachedText("N0");
    readonly CachedText scoreText = new CachedText("0");
    readonly CachedText bestScoreText = new CachedText("0");
    readonly CachedText rewardText = new CachedText(SignedFormat);
    readonly CachedText meanText = new CachedText(SignedFormat);
    readonly CachedText speedText = new CachedText("0.#'x'");

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
    Rect panelScreenRect;
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
            if (keyboard.minusKey.wasPressedThisFrame)
                SetUiScale(UiScale - UiScaleStep);
            if (keyboard.equalsKey.wasPressedThisFrame)
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
    }

    // Height of the panel in layout units; must match the rows drawn in OnGUI.
    float PanelHeight()
    {
        int statRows = 2 + (hasScore ? 2 : 0) + (rewardsUnknown ? 1 : 2);
        float chart = rewardsUnknown ? 0f : RowHeight + ChartHeight + Gap;
        return 2f * Padding + TitleHeight + RowHeight + Gap + statRows * RowHeight + Gap + chart
            + RowHeight + SliderHeight + Gap + ButtonHeight + Gap + ButtonHeight + Gap + FooterHeight;
    }

    void OnGUI()
    {
        if (!Visible || headless)
            return;

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
        float scale = Mathf.Min(screenHeight / ReferenceHeight * UiScale, screenHeight / (panelHeight + 2f * PanelY));
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
        if (GUI.Button(new Rect(sizeButtonsX + SizeButtonWidth + Gap, sizeButtonY, SizeButtonWidth, SizeButtonHeight), largerLabel, buttonStyle))
            SetUiScale(UiScale + UiScaleStep);
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

        GUI.Label(new Rect(x, y, width, FooterHeight), "H mostra ou esconde o painel", footerStyle);

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
}
