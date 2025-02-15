import React, { useState, useEffect } from "react";

const countries = [
  { name: "India", image: "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/India_Map.svg/500px-India_Map.svg.png" },
  { name: "USA", image: "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dc/USA_orthographic.svg/500px-USA_orthographic.svg.png" },
  { name: "France", image: "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/France_map_svg.svg/500px-France_map_svg.svg.png" },
  { name: "Japan", image: "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Japan_%28orthographic_projection%29.svg/500px-Japan_%28orthographic_projection%29.svg.png" }
];

function App() {
  const [currentCountry, setCurrentCountry] = useState({});
  const [userGuess, setUserGuess] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    getRandomCountry();
  }, []);

  const getRandomCountry = () => {
    const randomCountry = countries[Math.floor(Math.random() * countries.length)];
    setCurrentCountry(randomCountry);
    setMessage("");
    setUserGuess("");
  };

  const checkAnswer = () => {
    if (userGuess.trim().toLowerCase() === currentCountry.name.toLowerCase()) {
      setMessage("🎉 Correct! Loading next country...");
      setTimeout(getRandomCountry, 1500);
    } else {
      setMessage("❌ Incorrect, try again!");
    }
  };

  return (
    <div style={{ textAlign: "center", fontFamily: "Arial" }}>
      <h1>Guess the Country</h1>
      {currentCountry.image && <img src={currentCountry.image} alt="Country outline" width="300" />}
      <br />
      <input 
        type="text" 
        placeholder="Enter country name" 
        value={userGuess} 
        onChange={(e) => setUserGuess(e.target.value)} 
        style={{ padding: "8px", fontSize: "16px" }}
      />
      <button onClick={checkAnswer} style={{ marginLeft: "10px", padding: "8px", fontSize: "16px" }}>
        Submit
      </button>
      <p>{message}</p>
    </div>
  );
}

export default App;
