<div align="center">

# ✈️ AI Travel Planner

### Plan smarter. Travel better. ✨

An AI-powered travel planning application that creates personalized trip itineraries based on your destination, budget, travel style, interests, duration, and number of travelers.

<br>

![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql)
![Ollama](https://img.shields.io/badge/Ollama-AI-black?style=for-the-badge)

<br>

**🌍 Discover destinations · 🤖 Generate itineraries · 💰 Manage budgets · 🌦️ Check weather · 💾 Save trips**

</div>

---

## 🌟 About The Project

**AI Travel Planner** is a full-stack travel planning application designed to make trip planning faster and more personalized.

Instead of manually searching through dozens of websites, users can provide their travel preferences and let the application generate a complete travel plan.

The application combines an interactive frontend, a FastAPI backend, PostgreSQL persistence, AI-powered itinerary generation, and weather information into one platform.

---

## ✨ Features

### 🤖 AI-Powered Trip Planning

Generate personalized travel plans based on:

- 📍 Destination
- 🌎 Country
- 📅 Trip duration
- 👥 Number of travelers
- 💰 Budget
- 🎒 Travel style
- ❤️ Personal interests

---

### 🗺️ Personalized Itineraries

Get a structured day-by-day travel plan with:

- 📅 Daily activities
- 📍 Places to visit
- 🍜 Food recommendations
- 🎯 Activities
- 📝 Travel tips
- ⏱️ Suggested schedules

---

### 💰 Budget Breakdown

The generated trip includes an estimated budget breakdown for:

| Category | Included |
|---|---|
| 🍜 Food | ✅ |
| 🚗 Transport | ✅ |
| 🎯 Activities | ✅ |
| 🏨 Accommodation | ✅ |
| 📦 Miscellaneous | ✅ |

The application also compares estimated spending against the user's budget.

---

### 🌦️ Weather Information

The application integrates weather information to help travelers understand the conditions at their destination.

---

### 💾 Saved Trips

Users can save generated travel plans and access them later.

Saved trips include:

- Destination
- Country
- Duration
- Travelers
- Budget
- Travel style
- Generated itinerary
- Creation date

Trips can also be viewed and deleted directly from the application.

---

### 🎨 Modern UI

The frontend features a dark, modern interface with:

- Responsive layouts
- Interactive cards
- Smooth UI elements
- Travel-focused visual design
- Expandable saved-trip section
- Clean dashboard experience

---

## 🧠 How It Works

```text
                 ┌──────────────────┐
                 │      User        │
                 │ Travel Preferences│
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │   Next.js UI     │
                 │   React Frontend │
                 └────────┬─────────┘
                          │
                          ▼
                 ┌──────────────────┐
                 │     FastAPI      │
                 │     Backend      │
                 └───────┬───┬──────┘
                         │   │
             ┌───────────┘   └────────────┐
             ▼                            ▼
      ┌──────────────┐             ┌──────────────┐
      │ AI / Ollama  │             │   Weather    │
      │   Service    │             │   Service    │
      └──────┬───────┘             └──────────────┘
             │
             ▼
      ┌──────────────┐
      │  PostgreSQL  │
      │   Database   │
      └──────────────┘
