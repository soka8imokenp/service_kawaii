import { useState, useEffect } from 'react'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, '');

const getTelegramUser = () => {
  return window.Telegram?.WebApp?.initDataUnsafe?.user || {};
};

function App() {
  const initialText = "Salom. Nima kerakligini aytsangiz, men yordam berishga harakat qilaman.";
  
  const [dialogue, setDialogue] = useState(initialText);
  const [displayedText, setDisplayedText] = useState("");
  const [links, setLinks] = useState([]);
  
  const [userMessage, setUserMessage] = useState("");
  const [input, setInput] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [battery, setBattery] = useState(100);

  const [emotion, setEmotion] = useState('talking'); 
  const [frame, setFrame] = useState(1);
  
  // --- НОВОЕ: Состояние для кулдауна ---
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp) return;

    webApp.ready();
    webApp.expand();
  }, []);

  // Смена кадров для Lip-Sync
  useEffect(() => {
    let animInterval;
    
    if (isTyping) {
      if (emotion === 'talking') {
        setFrame(2);
        animInterval = setInterval(() => {
          setFrame(prev => (prev === 2 ? 3 : 2));
        }, 180); 
      } else {
        setFrame(1);
        let currentFrame = 1;
        animInterval = setInterval(() => {
          if (currentFrame < 3) {
            currentFrame++;
            setFrame(currentFrame);
          } else {
            clearInterval(animInterval);
          }
        }, 250); 
      }
    } else {
      setFrame(1);
    }

    return () => clearInterval(animInterval);
  }, [isTyping, emotion]);

  // Печатная машинка
  useEffect(() => {
    if (!dialogue) return;

    if (dialogue === "...") {
      setDisplayedText("...");
      setIsTyping(true);
      return;
    }

    const urlRegex = /(https?:\/\/[^\s]+)/g;
    const foundUrls = dialogue.match(urlRegex) || [];
    setLinks(foundUrls);

    const cleanText = dialogue.replace(urlRegex, '').trim();
    setIsTyping(true);
    setDisplayedText(""); 

    let currentText = "";
    let index = 0;

    const timer = setInterval(() => {
      if (index < cleanText.length) {
        currentText += cleanText[index]; 
        setDisplayedText(currentText);
        index++;
      } else {
        clearInterval(timer);
        setIsTyping(false);
      }
    }, 25);

    return () => clearInterval(timer);
  }, [dialogue]);

  const sendMessage = async () => {
    // Блокируем отправку, если идет загрузка, поле пустое ИЛИ работает кулдаун
    if (!input.trim() || isLoading || cooldown > 0) return;

    const textToSent = input.trim();
    setUserMessage(textToSent);
    setInput('');
    setIsLoading(true);
    setLinks([]);
    
    setEmotion('think');
    setDialogue("...");
    setBattery(prev => Math.max(5, prev - 10));

    try {
      const telegramUser = getTelegramUser();
      const response = await fetch(`${API_BASE_URL}/feedback/api/send/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textToSent,
          user_id: telegramUser.id || 123456789,
          username: telegramUser.username || '',
          first_name: telegramUser.first_name || '',
        }),
      });

      const data = await response.json();
      let cleanResponse = data.text.replace(/\*[^*]+\*/g, '').trim();
      
      if (data.emotion) {
         setEmotion(data.emotion);
      } else {
         setEmotion('talking');
      }

      setDialogue(cleanResponse);
    } catch {
      setEmotion('canthelp'); 
      setDialogue("Aloqa uzildi... Server javob bermayapti.");
    } finally {
      setIsLoading(false);

      // --- НОВОЕ: Запускаем таймер на 20 секунд после ответа ---
      setCooldown(20);
      const cooldownTimer = setInterval(() => {
        setCooldown((prev) => {
          if (prev <= 1) {
            clearInterval(cooldownTimer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
  };

  return (
    <div className="flex flex-col h-[100dvh] relative bg-[#05030a] font-ui selection:bg-fuchsia-500 selection:text-white overflow-hidden">
      
      {/* КИБЕР-ЭФФЕКТЫ */}
      <div className="cyber-grid pointer-events-none opacity-60"></div>
      <div className="scanlines pointer-events-none"></div>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#05030a]/40 to-[#05030a] z-10 pointer-events-none"></div>

      {/* --- HUD ПАНЕЛЬ --- */}
      <div className="relative z-20 flex justify-between items-start p-2 md:p-4">
        <div className="bg-[#0f0a1c]/90 backdrop-blur-md border-l-2 md:border-l-4 border-fuchsia-500 px-2 py-1 md:px-4 md:py-1.5 shadow-[2px_2px_0_rgba(0,0,0,0.5)] flex items-center gap-2">
          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-fuchsia-500 animate-pulse"></div>
          <h2 className="text-[8px] md:text-[10px] text-fuchsia-100 tracking-widest mt-0.5">SYS.ARCHIVE</h2>
        </div>
        
        <div className="bg-[#0f0a1c]/90 backdrop-blur-md border border-purple-900/50 p-1.5 md:p-2 shadow-[2px_2px_0_rgba(0,0,0,0.5)] flex flex-col items-end gap-1">
          <span className="text-[6px] md:text-[8px] text-purple-400 tracking-widest">BATTERY</span>
          <div className="flex gap-0.5 md:gap-1">
            {[...Array(5)].map((_, i) => (
              <div 
                key={i} 
                className={`w-2 h-1.5 md:w-3.5 md:h-2 transition-all duration-300 ${
                  i < Math.ceil(battery / 20) ? 'bg-fuchsia-500 shadow-[0_0_5px_#d946ef]' : 'bg-[#1b142c] border border-purple-900/50'
                }`}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* --- ЭКРАН ПЕРСОНАЖА (Стабильная зона) --- */}
      <div className="flex-1 relative z-10 flex flex-col justify-end items-center overflow-hidden">
        
        <img 
          src={`/service/${emotion}/${frame}.webp`} 
          alt={`Sumire-${emotion}`} 
          className="h-[58vh] md:h-[70vh] max-h-[580px] md:max-h-[750px] object-contain sprite-anim z-20 pointer-events-none select-none"
          onError={(e) => { e.target.src = '/sumire-full.png'; }}
        />
        
        {/* ОБЛАЧКО ЮЗЕРА */}
        {userMessage && (
          <div className="absolute top-8 right-2 md:right-4 max-w-[80%] md:max-w-[65%] z-30">
            <div className="bg-[#130b24]/95 backdrop-blur-md border border-fuchsia-500/50 p-2 md:p-3 shadow-[2px_2px_0_rgba(217,70,239,0.2)] text-right">
              <p className="font-dialogue text-[#e2e8f0] text-xs md:text-sm tracking-wide break-words">
                <span className="text-fuchsia-500 mr-1.5 opacity-80 font-ui text-[8px]">YOU:</span> 
                {userMessage}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* --- ДИАЛОГОВАЯ КОРОБКА (Намертво фиксированная!) --- */}
      <div className="relative z-30 px-2 md:px-6 pb-2 w-full max-w-4xl mx-auto flex-shrink-0">
        <div className="relative">
          {/* ИМЯ СУМИРЭ */}
          <div className="absolute -top-3 md:-top-4 left-4 bg-fuchsia-600 border border-fuchsia-300 px-3 md:px-6 py-1 z-40 shadow-[0_0_10px_rgba(217,70,239,0.6)]">
            <span className="text-[10px] md:text-xs text-white tracking-widest drop-shadow-[1px_1px_0_#000] mt-0.5 block">SUMIRE</span>
          </div>
          
          {/* Фиксированная высота: h-[130px] на мобилках, h-[160px] на мониторах */}
          <div className="bg-[#0a0710]/95 border-2 border-fuchsia-500/80 p-4 md:p-5 shadow-[4px_4px_0_rgba(0,0,0,0.8)] h-[130px] md:h-[160px] relative backdrop-blur-xl mt-2 flex flex-col justify-between">
            
            {/* Внутренний контейнер для текста со скрытым скроллом */}
            <div className="flex-1 overflow-y-auto no-scrollbar pr-1">
              <p className="font-dialogue text-[18px] md:text-[23px] text-[#e2e8f0] leading-tight md:leading-snug tracking-wide whitespace-pre-wrap">
                {displayedText}
              </p>

              {/* СИСТЕМНЫЕ ССЫЛКИ */}
              {!isTyping && links.length > 0 && (
                <div className="mt-2.5 flex gap-2 flex-wrap">
                  {links.map((link, i) => (
                    <a 
                      key={i} 
                      href={link} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="bg-[#1b142c] hover:bg-fuchsia-600 text-fuchsia-400 hover:text-white border border-fuchsia-500 text-[8px] md:text-[10px] px-3 py-1.5 transition-all shadow-[2px_2px_0_#d946ef] active:translate-y-0.5 active:translate-x-0.5 active:shadow-none flex items-center gap-2"
                    >
                      <span className="blink">▶</span> SYSTEM LINK
                    </a>
                  ))}
                </div>
              )}
            </div>

            {/* Маркер готовности (всегда прижат к правому нижнему углу бокса) */}
            {!isTyping && dialogue !== "..." && (
              <div className="absolute bottom-2 right-3 text-fuchsia-500 text-[10px] md:text-sm blink select-none">▼</div>
            )}
          </div>
        </div>
      </div>

      {/* --- ПАНЕЛЬ ВВОДА (Тоже не сжимает экран) --- */}
      <div className="relative z-30 px-2 md:px-6 pb-3 md:pb-5 w-full max-w-4xl mx-auto flex-shrink-0">
        <div className="bg-[#05030a]/95 border-2 border-purple-800 flex items-center p-1 md:p-1.5 shadow-[4px_4px_0_rgba(0,0,0,1)] focus-within:border-fuchsia-500 transition-all">
          <span className="text-fuchsia-500 font-dialogue text-xl md:text-2xl mx-2 blink">{' >'}</span>
          
          {/* Поле ввода остается активным, чтобы юзер мог набирать текст пока ждет */}
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Xabarni kiriting..." 
            disabled={isLoading}
            className="flex-1 bg-transparent mountaineer font-dialogue text-[#e2e8f0] text-base md:text-lg focus:outline-none placeholder-purple-900/70 w-full"
          />
          
          {/* --- НОВОЕ: Кнопка с обратным отсчетом --- */}
          <button 
            onClick={sendMessage}
            disabled={isLoading || !input.trim() || cooldown > 0}
            className={`ml-1 md:ml-2 text-white text-[8px] md:text-[10px] px-3 md:px-6 py-2.5 md:py-3 border border-fuchsia-300 shadow-[2px_2px_0_#000] transition-all
              ${cooldown > 0 
                ? 'bg-purple-900/50 text-gray-400 cursor-not-allowed opacity-70' 
                : 'bg-fuchsia-600 hover:bg-fuchsia-500 active:translate-y-0.5 active:translate-x-0.5 active:shadow-none'
              }`}
          >
            {cooldown > 0 ? `KUTING (${cooldown}s)` : 'YUBORISH'}
          </button>
        </div>
      </div>

    </div>
  )
}

export default App;
