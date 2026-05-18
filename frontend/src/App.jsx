import { useState, useEffect } from 'react'

function App() {
  // Прямое приветствие без глупых ролевых описаний
  const initialText = "Arxivga xush kelibsiz. Nima kerakligini aytsangiz, men yordam berishga harakat qilaman.";
  
  const [dialogue, setDialogue] = useState(initialText);
  const [displayedText, setDisplayedText] = useState("");
  const [links, setLinks] = useState([]);
  
  const [userMessage, setUserMessage] = useState("");
  const [input, setInput] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [battery, setBattery] = useState(100);

  useEffect(() => {
    let index = 0;
    setDisplayedText("");
    
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

    const timer = setInterval(() => {
      if (index < cleanText.length) {
        setDisplayedText((prev) => prev + cleanText.charAt(index));
        index++;
      } else {
        clearInterval(timer);
        setIsTyping(false);
      }
    }, 20);

    return () => clearInterval(timer);
  }, [dialogue]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const textToSent = input.trim();
    setUserMessage(textToSent);
    setInput('');
    setIsLoading(true);
    setLinks([]);
    
    setDialogue("...");
    setBattery(prev => Math.max(10, prev - 15));

    try {
      const response = await fetch('http://localhost:8000/feedback/api/send/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textToSent, user_id: 123456789 }),
      });

      const data = await response.json();
      
      // Чистим текст от любых звездочек, если они прилетели от ИИ
      let cleanResponse = data.text.replace(/\*[^*]+\*/g, '').trim();
      setDialogue(cleanResponse);
    } catch (error) {
      setDialogue("Aloqa uzildi. Server javob bermayapti...");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen relative bg-[#0b0813] font-ui">
      
      {/* Приглушенная анимированная 3D сетка */}
      <div className="animated-bg pointer-events-none opacity-40"></div>
      
      {/* Мягкое затемнение */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0b0813] via-transparent to-[#0b0813] pointer-events-none z-10"></div>

      {/* --- HUD ВЕРХНЯЯ ПАНЕЛЬ --- */}
      <div className="relative z-20 flex justify-between items-start p-4">
        <div className="bg-[#1b142c] border-2 border-[#6d28d9] px-3 py-1 shadow-[2px_2px_0_#000]">
          <h2 className="text-[10px] text-fuchsia-400 tracking-widest">ARCHIVE // LAYER</h2>
        </div>
        
        {/* Батарейка кубиками */}
        <div className="bg-[#1b142c] border-2 border-[#6d28d9] p-2 flex flex-col items-end gap-1 shadow-[2px_2px_0_#000]">
          <span className="text-[8px] text-purple-300 tracking-wider">SOCIAL BATTERY</span>
          <div className="flex gap-0.5">
            {[...Array(5)].map((_, i) => (
              <div 
                key={i} 
                className={`w-3 h-2 border border-black ${
                  i < Math.ceil(battery / 20) ? 'bg-fuchsia-500 shadow-[0_0_5px_#d946ef]' : 'bg-gray-900'
                }`}
              ></div>
            ))}
          </div>
        </div>
      </div>

      {/* --- ЭКРАН ПЕРСОНАЖА --- */}
      <div className="flex-1 relative z-10 flex flex-col justify-end items-center pb-2">
        {/* Мягкий аккуратный свет за ней */}
        <div className="absolute bottom-10 w-48 h-48 bg-fuchsia-500/10 rounded-full blur-[50px]"></div>
        
        <img 
          src="/sumire-full.png" 
          alt="Sumire" 
          className="h-[55vh] max-h-[450px] object-contain sprite-breathe z-20 drop-shadow-[0_0_15px_rgba(0,0,0,0.6)]"
        />
        
        {/* ОБЛАЧКО ИГРОКА (YOU) */}
        {userMessage && (
          <div className="absolute top-10 right-4 max-w-[65%] z-30">
            <div className="bg-[#1e1435] border-2 border-fuchsia-500 p-2.5 shadow-[4px_4px_0_#000] text-right relative">
              <div className="absolute -bottom-2 right-4 w-3 h-3 bg-[#1e1435] border-b-2 border-r-2 border-fuchsia-500 transform rotate-45"></div>
              <p className="text-fuchsia-300 text-xs tracking-wide">YOU: {userMessage}</p>
            </div>
          </div>
        )}
      </div>

      {/* --- ДИАЛОГОВЫЙ БОКС (Доработанный, сочный) --- */}
      <div className="relative z-30 px-3 pb-2">
        {/* ЯРКОЕ ИМЯ (Теперь горит неоном и отлично видно!) */}
        <div className="inline-block bg-[#6d28d9] border-2 border-white px-5 py-1 ml-4 relative top-1.5 z-40 shadow-[0_0_10px_#a855f7]">
          <span className="text-xs text-white tracking-widest font-bold drop-shadow-[2px_2px_0_#000]">SUMIRE</span>
        </div>
        
        {/* Главное окно текста */}
        <div className="bg-[#110c22]/95 border-4 border-purple-600 p-4 shadow-[6px_6px_0_#000] min-h-[110px] relative backdrop-blur-sm">
          {/* VT323 — Идеальный, крупный и крутой пиксельный шрифт для чтения */}
          <p className="font-dialogue text-[22px] sm:text-[24px] text-gray-100 leading-none tracking-wide min-h-[3rem]">
            {displayedText}
          </p>

          {/* ПОДХВАТ ССЫЛОК И КНОПКА */}
          {!isTyping && links.length > 0 && (
            <div className="mt-3 flex gap-2 flex-wrap">
              {links.map((link, i) => (
                <a 
                  key={i} 
                  href={link} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="bg-fuchsia-600 hover:bg-fuchsia-500 text-white font-bold text-xs px-5 py-2 border-2 border-white shadow-[3px_3px_0_#000] active:translate-y-0.5 active:shadow-none transition-all inline-flex items-center gap-2"
                >
                  ▶ OPEN LINK
                </a>
              ))}
            </div>
          )}

          {/* Мигающая стрелочка конца текста */}
          {!isTyping && dialogue !== "..." && (
            <div className="absolute bottom-2 right-4 text-fuchsia-400 text-xs animate-blink">▼</div>
          )}
        </div>
      </div>

      {/* --- ПАНЕЛЬ ВВОДА КОМАНД --- */}
      <div className="relative z-30 px-3 pb-4 mt-1">
        <div className="bg-black/90 border-2 border-purple-600 flex items-center p-1.5 shadow-[4px_4px_0_#000] focus-within:border-fuchsia-500 transition-colors">
          <span className="text-fuchsia-500 font-dialogue text-xl mx-2 animate-blink">{'>'}</span>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="TYPE COMMAND..." 
            disabled={isLoading}
            className="flex-1 bg-transparent text-white text-xs tracking-wider focus:outline-none placeholder-purple-900 uppercase"
          />
          <button 
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className="ml-2 bg-[#6d28d9] hover:bg-[#7c3aed] text-white text-[11px] font-bold px-4 py-2 border-2 border-purple-400 shadow-[2px_2px_0_#000] active:translate-y-0.5 active:shadow-none transition-all disabled:opacity-50"
          >
            ACT
          </button>
        </div>
      </div>

    </div>
  )
}

export default App;