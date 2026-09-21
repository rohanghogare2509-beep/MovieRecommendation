import streamlit as st
import pandas as pd
import requests
import pickle as pkl
import time
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Page Configuration - MUST BE FIRST
st.set_page_config(
    page_title="CineMatch AI  | Movie Recommender",
    layout="wide",
    page_icon="🎬",
    initial_sidebar_state="expanded"
)

# Custom CSS with modern styling
st.markdown("""
    <style>
    :root {
        --primary: #FF4B4B;
        --secondary: #1E1E1E;
        --dark: #0E1117;
        --light: #FFFFFF;
        --accent: #6E44FF;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background: var(--dark);
        color: var(--light);
    }
    
    .sidebar .sidebar-content {
        background: var(--secondary) !important;
        border-right: 1px solid #333;
    }
    
    .movie-card {
        border-radius: 12px;
        padding: 0;
        background: rgba(30, 30, 30, 0.8);
        transition: all 0.3s ease;
        overflow: hidden;
        height: 100%;
        position: relative;
        border: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        flex-direction: column;
    }
    
    .movie-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        background: rgba(40, 40, 40, 0.9);
    }
    
    .movie-poster {
        width: 100%;
        height: auto;
        object-fit: cover;
        transition: transform 0.5s ease;
        border-radius: 12px 12px 0 0;
    }
    
    .movie-card:hover .movie-poster {
        transform: scale(1.05);
    }
    
    .movie-info {
        padding: 15px;
        flex-grow: 1;
    }
    
    .movie-title {
        color: var(--light);
        font-weight: 600;
        font-size: 1rem;
        margin: 10px 0 5px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .movie-meta {
        color: #AAAAAA;
        font-size: 0.8rem;
        margin-bottom: 5px;
        display: flex;
        gap: 10px;
        align-items: center;
    }
    
    .movie-rating {
        display: inline-flex;
        align-items: center;
        color: gold;
    }
    
    .movie-overview {
        font-size: 0.85rem;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .header {
        background: linear-gradient(to right, var(--primary), var(--accent));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    .selected-movie-container {
        background: rgba(30, 30, 30, 0.8);
        border-radius: 15px;
        padding: 25px;
        margin-bottom: 30px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    }
    
    .spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
    }
    
    .empty-state {
        text-align: center;
        padding: 50px;
        opacity: 0.7;
    }
    
    .tag {
        display: inline-block;
        background: rgba(255,255,255,0.1);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        margin-right: 5px;
        margin-bottom: 5px;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
        .movie-card {
            flex-direction: column;
            margin-bottom: 20px;
        }
        
        .movie-poster {
            height: auto;
        }
        
        .movie-info {
            padding: 10px;
        }
        
        .movie-title {
            font-size: 0.9rem;
        }
        
        .movie-meta {
            font-size: 0.7rem;
        }
        
        .header {
            font-size: 1.5rem;
        }
        
        .selected-movie-container {
            padding: 15px;
        }
        
        .empty-state {
            padding: 30px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# Load data with caching
@st.cache_resource
def load_data():
    movies_dict = pkl.load(open('movies_dict.pkl', 'rb'))
    movies = pd.DataFrame(movies_dict)

    # Rebuild TF-IDF vectors from movie tags
    movies['tags'] = movies['tags'].fillna('').astype(str)

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english'
    )

    vectors = vectorizer.fit_transform(movies['tags'])

    return movies, vectors


movies, vectors = load_data()

# TMDB API integration with robust error handling
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_movie_details(movie_id):
    """Fetch movie details from OMDb API."""

    try:
        import requests

        # Get movie title from the movie dataset
        movie_rows = movies[movies["movie_id"] == movie_id]

        if movie_rows.empty:
            return None

        movie_title = movie_rows.iloc[0]["title"]

        # Remove year if the title contains one
        movie_title = str(movie_title).split(" (")[0].strip()

        api_key = st.secrets["OMDB_API_KEY"]

        url = "https://www.omdbapi.com/"
        params = {
            "apikey": api_key,
            "t": movie_title,
            "plot": "full"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get("Response") != "True":
            st.warning(
                f"OMDb could not find details for: {movie_title}"
            )
            return None

        return {
            "id": movie_id,
            "title": data.get("Title", movie_title),
            "poster": (
                data.get("Poster")
                if data.get("Poster") and data.get("Poster") != "N/A"
                else None
            ),
            "backdrop": None,
            "rating": data.get("imdbRating", "N/A"),
            "vote_count": data.get("imdbVotes", "N/A"),
            "tagline": "",
            "overview": data.get("Plot", "No description available."),
            "genres": data.get("Genre", ""),
            "director": data.get("Director", "N/A"),
            "actors": data.get("Actors", "N/A"),
            "release_date": data.get("Released", "N/A"),
            "year": data.get("Year", "N/A"),
            "runtime": data.get("Runtime", "N/A"),
            "imdb_id": data.get("imdbID"),
        }

    except Exception as e:
        st.error(
            f"Unexpected error for movie ID {movie_id}: {str(e)}"
        )
        return None

# Recommendation engine with fallback to local data
def recommend(selected_movie):
    """Get movie recommendations based on selected movie"""
    try:
        movie_index = movies[movies['title'] == selected_movie].index[0]

        # Calculate similarity only for the selected movie
        distances = cosine_similarity(
            vectors[movie_index],
            vectors
        ).flatten()

        movie_list = sorted(
            list(enumerate(distances)),
            reverse=True,
            key=lambda x: x[1]
        )[1:6]

        recommendations = []

        for i in movie_list:
            movie_id = movies.iloc[i[0]].movie_id
            details = fetch_movie_details(movie_id)

            if not details:  # Fallback to local data if API fails
                movie_data = movies.iloc[i[0]]
                details = {
                    'title': movie_data.title,
                    'year': movie_data.get('year', 'N/A'),
                    'genres': movie_data.get('genres', ''),
                    'overview': 'Details not available',
                    'rating': 0,
                    'poster': None
                }

            recommendations.append({
                'title': movies.iloc[i[0]].title,
                'id': movie_id,
                'details': details
            })

            # Add small delay between API calls
            time.sleep(0.2)

        return recommendations

    except IndexError:
        st.error("Movie not found in database")
        return []

    except Exception as e:
        st.error(f"Error generating recommendations: {str(e)}")
        return []

# Team Page Function
def show_team_page():
    st.markdown("""
    <div style="text-align: center; padding: 20px 0 30px;">
        <h1 style="margin-bottom: 10px;">👨‍💻 About the Developer</h1>
        <p style="opacity: 0.8; font-size: 1.1rem;">Built with AI, Machine Learning & Data Science</p>
    </div>
    """, unsafe_allow_html=True)

    # Team members data
    team_members = [
    {
        "name": "Rohan Ghogare",
        "role": "AI & Data Science Developer",
        "bio": "Passionate about Artificial Intelligence, Machine Learning and Data Analytics. Built this movie recommendation system using Python, Streamlit and machine learning.",
        "image": "https://raw.githubusercontent.com/Codeayu/MovieRecommendation/main/photos/rohan.jpg",
        "social": {
            "github": "https://github.com",
            "linkedin": "https://linkedin.com"
        }
    }
]
        
    # Create columns for team members
    cols = st.columns(1)
    for idx, member in enumerate(team_members):
        with cols[idx % 2]:
            st.markdown(f"""
            <div style="background: rgba(30, 30, 30, 0.8); border-radius: 12px; padding: 25px; margin-bottom: 20px; 
                        border: 1px solid rgba(255, 255, 255, 0.1); text-align: center; transition: all 0.3s ease;">
                <img src="{member['image']}" style="width: 160px; height: 160px; border-radius: 60%; object-fit: cover; 
                        border: 3px solid #FFD700; margin: 0 auto 15px; display: block;">
               <h3 style="margin-bottom: 5px; text-align: center; color: #FFD700;">
                   {member['name']}
               </h3>

               <p style="color: #FFFFFF; font-weight: 500; margin-bottom: 15px; text-align: center;">
                  {member['role']}
               </p>

               <p style="color: #FFFFFF; margin-bottom: 15px; text-align: center;">
                  {member['bio']}
               </p>
               <div style="display: flex; justify-content: center; gap: 10px;">
                    {"".join([f'<a href="{link}" target="_blank" style="color: var(--light); font-size: 1.2rem; transition: all 0.3s ease;">'
                              f'<img src="https://cdn.jsdelivr.net/npm/simple-icons@v7/icons/{platform}.svg" alt="{platform}" style="width: 24px; height: 24px; filter: invert(1);"></a>' 
                              for platform, link in member['social'].items()])}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background: rgba(110, 68, 255, 0.1); padding: 25px; border-radius: 12px; margin-top: 30px; text-align: center;">
        <h3>Project Mission</h3>
        <p style="opacity: 0.9; font-size: 1.1rem;">
            "We combine AI and creativity to solve real-world problems — starting with your movie night dilemmas!"
        </p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar Navigation
with st.sidebar:
    # Navigation
    
    # Logo and header
    st.markdown("""
        <div style="text-align: center; padding: 20px 0; margin-bottom: 30px;">
            <h1 style="margin-bottom: 0;">🎬  CineMatch AI</h1>
            <p style="opacity: 0.7; margin-top: 0;">Your AI-powered Movie Recommender</p>
        </div>
    """, unsafe_allow_html=True)
    page = st.radio("Navigate to:", ["Movie Recommender", "Meet The Developer"], label_visibility="collapsed")
    
    # Search box
    selected_movie = st.selectbox(
        "Search for a movie:",
        movies['title'].values,
        index=None,
        placeholder="Start typing to search...",
        key="movie_search"
    )
    
    # Recommendation button
    if st.button("Find Similar Movies", type="primary", use_container_width=True):
        st.session_state.show_recommendations = True
    else:
        if 'show_recommendations' not in st.session_state:
            st.session_state.show_recommendations = False
    
    # Featured section
    st.markdown("---")
    st.markdown("### 🔍 Featured Today")
    featured_movies = movies.sample(3)
    for _, movie in featured_movies.iterrows():
        with st.container():
            st.markdown(f"**{movie['title']}**")
            st.caption(f"{movie.get('genres', '')} • {movie.get('year', '')}")

# Main Content Area
if page == "Movie Recommender":
    st.markdown("<h1 class='header'>Discover Your Next Favorite Movie</h1>", unsafe_allow_html=True)
    st.markdown("""
        <div style='opacity: 0.8; margin-bottom: 30px; text-align: center;'>
            AI-powered recommendations based on your taste. Search for a movie you love and we'll find similar gems for you.
        </div>
    """, unsafe_allow_html=True)

    # Empty state or recommendations
    if not st.session_state.show_recommendations:
        # Welcome screen
        with st.container():
            st.markdown("""
                <div style="text-align: center; padding: 40px; background: rgba(255,255,255,0.03); 
                         border-radius: 15px; margin: 30px 0; border: 1px dashed rgba(255,255,255,0.1);">
                    <h3>How It Works</h3>
                    <div style="display: flex; justify-content: center; gap: 40px; margin: 30px 0;">
                        <div style="flex: 1; max-width: 200px;">
                            <div style="font-size: 2rem; margin-bottom: 10px;">1</div>
                            <p>Search for any movie you enjoy</p>
                        </div>
                        <div style="flex: 1; max-width: 200px;">
                            <div style="font-size: 2rem; margin-bottom: 10px;">2</div>
                            <p>Click "Find Similar Movies"</p>
                        </div>
                        <div style="flex: 1; max-width: 200px;">
                            <div style="font-size: 2rem; margin-bottom: 10px;">3</div>
                            <p>Discover your next favorites</p>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # Trending movies section
        st.markdown("### 🎥 Trending Now")
        trending_movies = movies.sample(5)
        cols = st.columns(5)
        for idx, (_, movie) in enumerate(trending_movies.iterrows()):
            with cols[idx]:
                details = fetch_movie_details(movie['movie_id'])
                if not details:  # Fallback to local data
                    details = {
                        'poster': None,
                        'title': movie['title'],
                        'rating': 0,
                        'year': movie.get('year', 'N/A')
                    }
                
                st.markdown(f"""
                    <div class="movie-card">
                        <img src="{details['poster'] if details['poster'] else 'https://via.placeholder.com/300x450?text=No+Poster'}" 
                             class="movie-poster">
                        <div class="movie-info">
                            <div class="movie-title">{movie['title']}</div>
                            <div class="movie-meta">
                                <span class="movie-rating">⭐ {details['rating']}</span>
                                <span>{details['year']}</span>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

    elif selected_movie:
        # Loading state
        with st.spinner('Analyzing your movie taste...'):
            time.sleep(0.5)  # Simulate loading for better UX
            
            recommendations = recommend(selected_movie)
            
            if recommendations:
                # Selected movie showcase
                selected_movie_data = movies[movies['title'] == selected_movie].iloc[0]
                selected_details = fetch_movie_details(selected_movie_data['movie_id'])
                
                if not selected_details:  # Fallback to local data
                    selected_details = {
                        'title': selected_movie_data['title'],
                        'year': selected_movie_data.get('year', 'N/A'),
                        'genres': selected_movie_data.get('genres', ''),
                        'overview': 'Details not available',
                        'rating': 0,
                        'poster': None,
                        'vote_count': 0,
                        'release_date': '',
                        'runtime': 'N/A',
                        'tagline': '',
                        'imdb_id': ''
                    }
                
                st.markdown(f"<h2>Because you liked: <span style='color: var(--primary)'>{selected_movie}</span></h2>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    if selected_details['poster']:
                        st.image(selected_details['poster'])
                    else:
                        st.image('https://via.placeholder.com/300x450?text=No+Poster')
                
                with col2:
                    st.markdown(f"**Rating:** ⭐ {selected_details['rating']} ({selected_details['vote_count']} votes)")
                    st.markdown(f"**Release Date:** {selected_details['release_date']}")
                    st.markdown(f"**Runtime:** {selected_details['runtime']}")
                    st.markdown(f"**Genres:** {selected_details['genres']}")
                    
                    if selected_details['tagline']:
                        st.markdown(f"*\"{selected_details['tagline']}\"*")
                    
                    if selected_details['overview']:
                        with st.expander("Overview"):
                            st.write(selected_details['overview'])
                    
                    if selected_details['imdb_id']:
                        st.markdown(f"[View on IMDB](https://www.imdb.com/title/{selected_details['imdb_id']})", unsafe_allow_html=True)
                
                # Recommendations section
                st.markdown(f"<h2 style='margin-top: 40px;'>You Might Also Enjoy</h2>", unsafe_allow_html=True)
                
                cols = st.columns(5)
                for idx, movie in enumerate(recommendations):
                    with cols[idx % 5]:
                        if movie['details']:
                            st.markdown(f"""
                                <div class="movie-card">
                                    <img src="{movie['details']['poster'] if movie['details']['poster'] else 'https://via.placeholder.com/300x450?text=No+Poster'}" 
                                         class="movie-poster">
                                    <div class="movie-info">
                                        <div class="movie-title">{movie['title']}</div>
                                        <div class="movie-meta">
                                            <span class="movie-rating">⭐ {movie['details']['rating']}</span>
                                            <span>{movie['details']['year']}</span>
                                        </div>
                                        <div class="movie-overview" title="{movie['details']['overview']}">
                                            {movie['details']['overview']}
                                        </div>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
            else:
                # Empty state for no recommendations
                st.markdown("""
                    <div class="empty-state">
                        <img src="https://cdn-icons-png.flaticon.com/512/4076/4076478.png" alt="No results" width="100">
                        <h3>No Recommendations Found</h3>
                        <p>We couldn't find similar movies for your selection.</p>
                        <p>Try another movie you enjoy!</p>
                    </div>
                """, unsafe_allow_html=True)

elif page == "Meet The Developer":
    show_team_page()

