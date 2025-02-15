import { useEffect, useState } from "react";
import * as d3 from "d3";

function App() {
  const [countries, setCountries] = useState([]);
  const [currentCountry, setCurrentCountry] = useState(null);
  const [userGuess, setUserGuess] = useState("");
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);



  const width = 600;
  const height = 400;

  useEffect(() => {
    fetch("/countries.geo.json")
      .then((res) => res.json())
      .then((data) => {

        const countryList = data.features.filter((feature) => {
          const countryName = feature.properties.name;

          const excludedCountries = [
            "New Caledonia", "French Guiana", "Guadeloupe", "Martinique", "Reunion", "Mayotte", "Saint Pierre and Miquelon","French Southern and Antarctic Lands"
          ];
          return !excludedCountries.includes(countryName);
        }).map((feature) => ({
          name: feature.properties.name,
          outline: feature.geometry,
        }));
        setCountries(countryList);
        getNewCountry(countryList);
      })
      .catch((err) => console.error("Error loading dataset:", err));
  }, []);

  useEffect(() => {
    if (currentCountry) {
      const svg = d3
        .select("#map")
        .attr("width", width)
        .attr("height", height);

      const projection = d3.geoMercator().fitSize([width, height], currentCountry.outline);
      const path = d3.geoPath().projection(projection);

      svg.selectAll("*").remove();

      svg
        .append("path")
        .datum(currentCountry.outline)
        .attr("d", path)
        .attr("fill", "transparent")

        .attr("stroke-width", 2)
        .attr("stroke-linejoin", "round");
    }
  }, [currentCountry]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (userGuess.toLowerCase() === currentCountry.name.toLowerCase()) {
      setFeedback("Correct!");
      setScore(score + 1);
      getNewCountry(countries);
    } else {
      setFeedback("Try again!");
    }

  };

  const getNewCountry = (countryList) => {
    const randomIndex = Math.floor(Math.random() * countryList.length);
    setCurrentCountry(countryList[randomIndex]);



  };

  const handleGiveUp = () => {

  };

  const handleNext = () => {
    setShowAnswer(false);
    setUserGuess("");



  };

  const handleHint = () => {
    if (hintIndex < currentCountry.name.length) {


    }
  };

  return (
    <div style={{ backgroundColor: "#0f0f0f", color: "#fff", minHeight: "100vh", padding: "20px", fontFamily: "'Roboto', sans-serif" }}>
      <h1 style={{ textAlign: "center", color: "#00f0ff", fontSize: "36px", marginBottom: "20px" }}>Guess the Country</h1>
      {currentCountry ? (
        <div style={{ textAlign: "center" }}>
          <p style={{ fontSize: "20px", color: "#00f0ff" }}>What country is this?</p>
          <svg id="map" style={{ border: "2px solid #00f0ff", borderRadius: "10px" }} />
          <form onSubmit={handleSubmit} style={{ marginTop: "20px" }}>
            <input
              type="text"
              value={userGuess}
              onChange={(e) => setUserGuess(e.target.value)}
              placeholder="Enter country name"
              style={{
                padding: "12px",
                fontSize: "18px",
                width: "320px",
                margin: "10px 0",
                borderRadius: "5px",
                border: "1px solid #444",
                backgroundColor: "#222",
                color: "#fff",
                boxShadow: "0px 0px 8px rgba(0, 255, 255, 0.5)",
                transition: "0.3s ease",
              }}
            />
            <br />
            <button
              type="submit"
              style={{
                padding: "12px 25px",
                fontSize: "18px",
                backgroundColor: "#444",
                color: "#fff",
                border: "none",
                borderRadius: "5px",
                cursor: "pointer",
                margin: "5px",
                boxShadow: "0px 0px 8px rgba(0, 255, 255, 0.5)",
                transition: "0.3s ease",
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = "#00f0ff"}
              onMouseOut={(e) => e.target.style.backgroundColor = "#444"}
            >
              Submit
            </button>
          </form>
          <br />
          <button
            onClick={handleGiveUp}
            style={{
              padding: "12px 25px",
              fontSize: "18px",
              backgroundColor: "#444",
              color: "#fff",
              border: "none",
              borderRadius: "5px",
              cursor: "pointer",
              margin: "5px",
              boxShadow: "0px 0px 8px rgba(0, 255, 255, 0.5)",
              transition: "0.3s ease",
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = "#00f0ff"}
            onMouseOut={(e) => e.target.style.backgroundColor = "#444"}
          >
            Give Up
          </button>
          {showAnswer && (
            <div style={{ marginTop: "20px", fontSize: "18px" }}>
              <p>The correct answer is: {currentCountry.name}</p>
              <button
                onClick={handleNext}
                style={{
                  padding: "12px 25px",
                  fontSize: "18px",
                  backgroundColor: "#444",
                  color: "#fff",
                  border: "none",
                  borderRadius: "5px",
                  cursor: "pointer",
                  margin: "5px",
                  boxShadow: "0px 0px 8px rgba(0, 255, 255, 0.5)",
                  transition: "0.3s ease",
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = "#00f0ff"}
                onMouseOut={(e) => e.target.style.backgroundColor = "#444"}
              >
                Next
              </button>
            </div>
          )}
          {!showAnswer && (
            <button
              onClick={handleHint}
              style={{
                padding: "12px 25px",
                fontSize: "18px",
                backgroundColor: "#444",
                color: "#fff",
                border: "none",
                borderRadius: "5px",
                cursor: "pointer",
                margin: "5px",
                boxShadow: "0px 0px 8px rgba(0, 255, 255, 0.5)",
                transition: "0.3s ease",
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = "#00f0ff"}
              onMouseOut={(e) => e.target.style.backgroundColor = "#444"}
            >
              Hint
            </button>
          )}
          <p style={{ fontSize: "18px", color: "#f0f0f0" }}>{feedback}</p>
          <p style={{ fontSize: "20px", color: "#00f0ff" }}>Score: {score}</p>
          {hint && <p style={{ fontSize: "18px", color: "#f0f0f0" }}>Hint: {hint}</p>} {/* Display the hint */}
        </div>
      ) : (
        <p>Loading...</p>
      )}
    </div>
  );
}

export default App;
