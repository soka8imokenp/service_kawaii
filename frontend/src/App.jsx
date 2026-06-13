import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, '');

const getTelegramUser = () => {
  try {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      try {
        if (typeof tg.requestFullscreen === 'function') {
          tg.requestFullscreen();
        }
      } catch (fsErr) {
        console.warn('requestFullscreen is not supported on this client version:', fsErr);
      }
      const user = tg.initDataUnsafe?.user;
      if (user && user.id) {
        return user;
      }
    }
  } catch (e) {
    console.error('Telegram WebApp init error:', e);
  }
  return {};
};

// --- Haptic Feedback (Вибрация для Telegram) ---
const triggerHaptic = (type = 'light') => {
  const tg = window.Telegram?.WebApp;
  if (tg && tg.HapticFeedback) {
    if (type === 'light' || type === 'medium' || type === 'heavy') {
      tg.HapticFeedback.impactOccurred(type);
    } else if (['error', 'success', 'warning'].includes(type)) {
      tg.HapticFeedback.notificationOccurred(type);
    }
  }
};

function App() {
  const initialText = "Salom. Nima kerakligini aytsangiz, men yordam berishga harakat qilaman.";
  
  const [dialogue, setDialogue] = useState(initialText);
  const [displayedText, setDisplayedText] = useState("");
  
  const [buttons, setButtons] = useState([]);
  const [animeList, setAnimeList] = useState([]);
  
  const [userMessage, setUserMessage] = useState("");
  const [input, setInput] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [battery, setBattery] = useState(100);

  const [emotion, setEmotion] = useState('talking'); 
  const [frame, setFrame] = useState(1);
  const [cooldown, setCooldown] = useState(0);

  const bgMusicRef = useRef(null);
  const [bgmStarted, setBgmStarted] = useState(false);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (webApp) {
      webApp.ready();
      webApp.expand();
      try {
        if (typeof webApp.requestFullscreen === 'function') {
          webApp.requestFullscreen();
        }
      } catch (fsErr) {
        console.warn('requestFullscreen is not supported on this client:', fsErr);
      }
    }

    bgMusicRef.current = new Audio('/audio/bgsound.opus');
    bgMusicRef.current.loop = true;
    bgMusicRef.current.volume = 0.1;
  }, []);

  const handleFirstInteraction = () => {
    if (!bgmStarted && bgMusicRef.current) {
      bgMusicRef.current.play().catch(() => {});
      setBgmStarted(true);
    }
  };

  useEffect(() => {
    const rechargeInterval = setInterval(() => {
      setBattery(prev => (prev < 100 ? prev + 1 : 100));
    }, 2000); 
    return () => clearInterval(rechargeInterval);
  }, []);

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
        }, 350); 
      }
    } else {
      setFrame(1);
    }
    return () => clearInterval(animInterval);
  }, [isTyping, emotion]);

  useEffect(() => {
    if (!dialogue) return;

    if (dialogue === "...") {
      setDisplayedText("...");
      setIsTyping(true);
      return;
    }

    setIsTyping(true);
    setDisplayedText(""); 

    let currentText = "";
    let index = 0;
    const startTime = Date.now();
    const MIN_ANIMATION_TIME = 1500; 
    let timeoutId;

    const timer = setInterval(() => {
      if (index < dialogue.length) {
        currentText += dialogue[index]; 
        setDisplayedText(currentText);
        index++;
      } else {
        clearInterval(timer);
        const elapsed = Date.now() - startTime;
        const remainingTime = Math.max(0, MIN_ANIMATION_TIME - elapsed);
        
        timeoutId = setTimeout(() => {
          setIsTyping(false); 
        }, remainingTime);
      }
    }, 25); 

    return () => {
      clearInterval(timer);
      clearTimeout(timeoutId);
    };
  }, [dialogue]);

  const sendMessage = async () => {
    handleFirstInteraction(); 
    
    if (!input.trim() || isLoading || cooldown > 0 || battery < 25) return;

    const textToSent = input.trim();
    setUserMessage(textToSent);
    setInput('');
    setIsLoading(true);
    
    setButtons([]); 
    setAnimeList([]);
    
    setEmotion('think');
    setDialogue("...");
    setBattery(prev => Math.max(0, prev - 25));

    triggerHaptic('medium');

    try {
      const telegramUser = getTelegramUser();
      const response = await fetch(`${API_BASE_URL}/feedback/api/send/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: textToSent,
          user_id: telegramUser.id || 0,
          username: telegramUser.username || '',
          first_name: telegramUser.first_name || '',
        }),
      });

      const data = await response.json();
      
      let cleanResponse = data.text
        .replace(/<[^>]*>?/gm, '') 
        .replace(/\*[^*]+\*/g, '') 
        .trim();
      
      setEmotion(data.emotion || 'talking');
      
      if (data.buttons) setButtons(data.buttons);
      if (data.anime_list) setAnimeList(data.anime_list);

      setDialogue(cleanResponse);
      triggerHaptic('success'); 

    } catch {
      setEmotion('canthelp'); 
      setDialogue("Aloqa uzildi... Server javob bermayapti.");
      triggerHaptic('error'); 
    } finally {
      setIsLoading(false);

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

  const sendActionMessage = async (text) => {
    handleFirstInteraction(); 
    if (isLoading) return;

    setUserMessage(text);
    setInput('');
    setIsLoading(true);
    
    setButtons([]); 
    setAnimeList([]);
    
    setEmotion('think');
    setDialogue("...");
    setBattery(prev => Math.max(0, prev - 25));

    triggerHaptic('medium');

    try {
      const telegramUser = getTelegramUser();
      const response = await fetch(`${API_BASE_URL}/feedback/api/send/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: text,
          user_id: telegramUser.id || 0,
          username: telegramUser.username || '',
          first_name: telegramUser.first_name || '',
        }),
      });

      const data = await response.json();
      
      let cleanResponse = data.text
        .replace(/<[^>]*>?/gm, '') 
        .replace(/\*[^*]+\*/g, '') 
        .trim();
      
      setEmotion(data.emotion || 'talking');
      
      if (data.buttons) setButtons(data.buttons);
      if (data.anime_list) setAnimeList(data.anime_list);

      setDialogue(cleanResponse);
      triggerHaptic('success'); 

    } catch {
      setEmotion('canthelp'); 
      setDialogue("Aloqa uzildi... Server javob bermayapti.");
      triggerHaptic('error'); 
    } finally {
      setIsLoading(false);

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

  const isBatteryLow = battery < 25;

  // Настройки пружинной анимации для карточек аниме
  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.12 }
    }
  };

  const itemVariants = {
    hidden: { y: 20, opacity: 0, scale: 0.95 },
    show: { 
      y: 0, 
      opacity: 1, 
      scale: 1,
      transition: { type: "spring", stiffness: 100, damping: 14 } 
    }
  };

  return (
    <div onClick={handleFirstInteraction} className="flex flex-col h-full relative bg-[#05030a] font-ui selection:bg-fuchsia-500 selection:text-white overflow-hidden cursor-default">
      
      <div className="cyber-grid pointer-events-none opacity-60"></div>
      <div className="scanlines pointer-events-none"></div>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#05030a]/40 to-[#05030a] z-10 pointer-events-none"></div>

      {/* HUD ПАНЕЛЬ */}
      <div style={{ paddingTop: 'calc(var(--tg-safe-area-inset-top, 0px) + 42px)' }} className="relative z-20 flex justify-between items-start px-2 pb-2 md:p-4">
        <div className="bg-[#0f0a1c]/90 backdrop-blur-md border-l-2 md:border-l-4 border-fuchsia-500 px-2 py-1 md:px-4 md:py-1.5 shadow-[2px_2px_0_rgba(0,0,0,0.5)] flex items-center gap-2">
          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-fuchsia-500 animate-pulse"></div>
          <h2 className="text-[8px] md:text-[10px] text-fuchsia-100 tracking-widest mt-0.5">SYS.ARCHIVE</h2>
        </div>
        
        <div className={`bg-[#0f0a1c]/90 backdrop-blur-md border p-1.5 md:p-2 shadow-[2px_2px_0_rgba(0,0,0,0.5)] flex flex-col items-end gap-1 transition-colors ${isBatteryLow ? 'border-red-900/80 animate-pulse' : 'border-purple-900/50'}`}>
          <span className={`text-[6px] md:text-[8px] tracking-widest ${isBatteryLow ? 'text-red-500' : 'text-purple-400'}`}>
            BATTERY {battery}%
          </span>
          <div className="flex gap-0.5 md:gap-1">
            {[...Array(5)].map((_, i) => (
              <div 
                key={i} 
                className={`w-2 h-1.5 md:w-3.5 md:h-2 transition-all duration-500 ${
                  i < Math.ceil(battery / 20) 
                    ? (isBatteryLow ? 'bg-red-500 shadow-[0_0_5px_#ef4444]' : 'bg-fuchsia-500 shadow-[0_0_5px_#d946ef]') 
                    : 'bg-[#1b142c] border border-purple-900/50'
                }`}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* ЭКРАН ПЕРСОНАЖА */}
      <div className="flex-1 relative z-10 flex flex-col justify-end items-center overflow-visible">
        <img 
          src={`/service/${emotion}/${frame}.webp`} 
          alt={`Sumire-${emotion}`} 
          className="h-[58vh] md:h-[70vh] max-h-[580px] md:max-h-[750px] object-contain sprite-anim z-20 pointer-events-none select-none"
          onError={(e) => { e.target.src = '/sumire-full.png'; }}
        />
        
        <AnimatePresence>
          {userMessage && (
            <motion.div 
              initial={{ opacity: 0, x: 30, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20 }}
              className="absolute top-8 right-2 md:right-4 max-w-[80%] md:max-w-[65%] z-30"
            >
              <div className="bg-[#130b24]/95 backdrop-blur-md border border-fuchsia-500/50 p-2 md:p-3 shadow-[2px_2px_0_rgba(217,70,239,0.2)] text-right">
                <p className="font-dialogue text-[#e2e8f0] text-xs md:text-sm tracking-wide break-words">
                  <span className="text-fuchsia-500 mr-1.5 opacity-80 font-ui text-[8px]">YOU:</span> 
                  {userMessage}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ДИАЛОГОВАЯ КОРОБКА */}
      <div className="relative z-30 px-2 md:px-6 pb-2 w-full max-w-4xl mx-auto flex-shrink-0">
        <div className="relative">
          <div className="absolute -top-3 md:-top-4 left-4 bg-fuchsia-600 border border-fuchsia-300 px-3 md:px-6 py-1 z-40 shadow-[0_0_10px_rgba(217,70,239,0.6)]">
            <span className="text-[10px] md:text-xs text-white tracking-widest drop-shadow-[1px_1px_0_#000] mt-0.5 block">SUMIRE</span>
          </div>
          
          <div className="bg-[#0a0710]/95 border-2 border-fuchsia-500/80 p-4 md:p-5 shadow-[4px_4px_0_rgba(0,0,0,0.8)] h-[130px] md:h-[160px] relative backdrop-blur-xl mt-2 flex flex-col">
            <div className="flex-1 overflow-y-auto no-scrollbar pr-1">
              <p className={`font-dialogue text-[18px] md:text-[23px] text-[#e2e8f0] leading-tight md:leading-snug tracking-wide whitespace-pre-wrap ${isBatteryLow && dialogue !== "..." ? 'opacity-80' : ''}`}>
                {isBatteryLow && dialogue !== "..." && !isTyping ? "*(Quvvat past...)*\n" + displayedText : displayedText}
              </p>

              {/* БЛОК С АНИМЕ (АНИМАЦИЯ ПОЯВЛЕНИЯ КАРТОЧЕК ОДНА ЗА ДРУГОЙ) */}
              {!isTyping && animeList.length > 0 && (
                <motion.div 
                  variants={containerVariants}
                  initial="hidden"
                  animate="show"
                  className="mt-3 flex flex-col gap-2"
                >
                  {animeList.map((anime, i) => (
                    <motion.div 
                      key={i} 
                      variants={itemVariants}
                      whileHover={{ backgroundColor: "rgba(19, 11, 36, 0.8)", borderColor: "rgba(217, 70, 239, 0.5)" }}
                      className="flex justify-between items-center bg-[#130b24]/60 border border-purple-900/50 p-2 shadow-sm"
                    >
                      <span className="text-[#e2e8f0] text-sm md:text-base font-dialogue tracking-wide pr-2 flex items-center">
                        <svg 
                          width="20" 
                          height="20" 
                          viewBox="0 0 24 24" 
                          fill="none" 
                          xmlns="http://www.w3.org/2000/svg"
                          className="text-fuchsia-500 mr-2 shrink-0"
                        >
                          <path d="M19.25 3H4.75A2.755 2.755 0 0 0 2 5.75v9.5A2.755 2.755 0 0 0 4.75 18h4.54l-.5 1.5H7.495V21h9v-1.5H15.2l-.5-1.5h4.54a2.755 2.755 0 0 0 2.75-2.75v-9.5A2.755 2.755 0 0 0 19.24 3h.01Zm-5.625 16.5h-3.25l.5-1.5h2.255l.5 1.5h-.005Zm6.875-4.25c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-9.5c0-.69.56-1.25 1.25-1.25h14.5c.69 0 1.25.56 1.25 1.25v9.5Z" fill="currentColor"/>
                        </svg>
                        <span className="line-clamp-2">{anime.name}</span>
                      </span>
                      <motion.a 
                        href={anime.url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="flex-shrink-0 bg-[#1b142c] hover:bg-fuchsia-600 text-fuchsia-400 hover:text-white border border-fuchsia-500 text-[8px] md:text-[10px] px-3 py-1.5 transition-all shadow-[2px_2px_0_#d946ef] flex items-center gap-1.5 whitespace-nowrap"
                      >
                        <span className="blink">▶</span> KO'RISH
                      </motion.a>
                    </motion.div>
                  ))}
                </motion.div>
              )}

              {!isTyping && buttons.length > 0 && (
                <div className="mt-4 flex flex-col gap-3 pb-2">
                  {buttons.map((btn, i) => {
                    const isLink = !!btn.url;
                    if (isLink) {
                      return (
                        <motion.a 
                          key={i} 
                          href={btn.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ type: "spring", delay: 0.2 }}
                          whileHover={{ borderColor: "rgba(6,182,212,0.9)", boxShadow: "0px 0px 8px rgba(6,182,212,0.6)" }}
                          whileTap={{ scale: 0.99 }}
                          className="group relative flex items-center justify-center gap-3 w-full bg-[#05030a]/80 border-2 border-cyan-500/70 hover:border-cyan-400 text-cyan-400 hover:text-cyan-200 text-[10px] md:text-xs font-ui px-4 py-2.5 transition-all shadow-[4px_4px_0_rgba(6,182,212,0.5)] cursor-pointer"
                        >
                          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-cyan-500 animate-pulse"></div>
                          <span className="tracking-widest drop-shadow-[0_0_5px_rgba(6,182,212,0.8)]">
                            {btn.text.toUpperCase()}
                          </span>
                          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-cyan-500 animate-pulse"></div>
                        </motion.a>
                      );
                    } else {
                      return (
                        <motion.button 
                          key={i} 
                          onClick={() => sendActionMessage(btn.text)}
                          initial={{ opacity: 0, scale: 0.95 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ type: "spring", delay: 0.2 }}
                          whileHover={{ borderColor: "rgba(217,70,239,0.9)", boxShadow: "0px 0px 8px rgba(217,70,239,0.6)", color: "#fdf4ff" }}
                          whileTap={{ scale: 0.99 }}
                          className="group relative flex items-center justify-center gap-3 w-full bg-[#05030a]/80 border-2 border-fuchsia-500/70 text-fuchsia-400 text-[10px] md:text-xs font-ui px-4 py-2.5 transition-all shadow-[4px_4px_0_rgba(217,70,239,0.5)] cursor-pointer"
                        >
                          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-fuchsia-500 animate-pulse"></div>
                          <span className="tracking-widest drop-shadow-[0_0_5px_rgba(217,70,239,0.8)]">
                            {btn.text.toUpperCase()}
                          </span>
                          <div className="w-1.5 h-1.5 md:w-2 md:h-2 bg-fuchsia-500 animate-pulse"></div>
                        </motion.button>
                      );
                    }
                  })}
                </div>
              )}
            </div>

            {!isTyping && dialogue !== "..." && (
              <div className="absolute bottom-2 right-3 text-fuchsia-500 text-[10px] md:text-sm blink select-none">▼</div>
            )}
          </div>
        </div>
      </div>

      {/* ПАНЕЛЬ ВВОДА */}
      <div className="relative z-30 px-2 md:px-6 pb-3 md:pb-5 w-full max-w-4xl mx-auto flex-shrink-0">
        <div className={`bg-[#05030a]/95 border-2 flex items-center p-1 md:p-1.5 shadow-[4px_4px_0_rgba(0,0,0,1)] transition-all ${isBatteryLow ? 'border-red-900/50' : 'border-purple-800 focus-within:border-fuchsia-500'}`}>
          <span className={`${isBatteryLow ? 'text-red-500' : 'text-fuchsia-500'} font-dialogue text-xl md:text-2xl mx-2 blink`}>{' >'}</span>
          
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            onFocus={handleFirstInteraction}
            placeholder={isBatteryLow ? "Quvvat yetarli emas..." : "Xabarni kiriting..."} 
            disabled={isLoading || isBatteryLow}
            className="flex-1 bg-transparent mountaineer font-dialogue text-[#e2e8f0] text-base md:text-lg focus:outline-none placeholder-purple-900/70 w-full disabled:opacity-50"
          />
          
          <motion.button 
            onClick={sendMessage}
            disabled={isLoading || !input.trim() || cooldown > 0 || isBatteryLow}
            whileHover={(!isLoading && !isBatteryLow && cooldown === 0 && input.trim()) ? { scale: 1.02 } : {}}
            whileTap={(!isLoading && !isBatteryLow && cooldown === 0 && input.trim()) ? { scale: 0.98 } : {}}
            className={`ml-1 md:ml-2 text-white text-[8px] md:text-[10px] px-3 md:px-6 py-2.5 md:py-3 border shadow-[2px_2px_0_#000] transition-all
              ${isBatteryLow 
                ? 'bg-red-900/30 border-red-900/50 text-red-500 cursor-not-allowed'
                : cooldown > 0 
                  ? 'bg-purple-900/50 border-fuchsia-300 text-gray-400 cursor-not-allowed opacity-70' 
                  : 'bg-fuchsia-600 border-fuchsia-300 hover:bg-fuchsia-500'
              }`}
          >
            {isBatteryLow 
              ? `QUVVAT (${battery}%)` 
              : cooldown > 0 
                ? `KUTING (${cooldown}s)` 
                : 'YUBORISH'}
          </motion.button>
        </div>
      </div>
    </div>
  )
}

export default App;