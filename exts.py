// frontend/src/components/Navbar.js
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import axios from 'axios';
import API_URL from '../config';

function Navbar({ isLoggedIn, adminData, setShowLogin, setShowRegister, handleLogout }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const [profileImageUrl, setProfileImageUrl] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [trendingData, setTrendingData] = useState([]);
  const [trendingIndex, setTrendingIndex] = useState(0);
  const [loadingTrending, setLoadingTrending] = useState(true);
  const [isHovering, setIsHovering] = useState(false);
  const [animationKey, setAnimationKey] = useState(0);
  const [dataType, setDataType] = useState('trending');

  const [showTopbar, setShowTopbar] = useState(true);
  const [lastScrollY, setLastScrollY] = useState(0);
  const [scrolled, setScrolled] = useState(false);

  const [navCategories, setNavCategories] = useState([]);
  const [loadingCategories, setLoadingCategories] = useState(true);

  // --- Scroll handler (unchanged) ---
  useEffect(() => {
    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      if (currentScrollY > lastScrollY && currentScrollY > 100) {
        setShowTopbar(false);
      } else if (currentScrollY < lastScrollY) {
        setShowTopbar(true);
      }
      setScrolled(currentScrollY > 50);
      setLastScrollY(currentScrollY);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [lastScrollY]);

  // --- Fetch trending news ---
  useEffect(() => {
    fetchTrendingNews();
    const refreshInterval = setInterval(fetchTrendingNews, 2 * 60 * 1000);
    return () => clearInterval(refreshInterval);
  }, []);

  // --- Fetch categories for navigation ---
  useEffect(() => {
    fetchNavCategories();
  }, []);

  const fetchNavCategories = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/nav-categories`, {
        withCredentials: true
      });
      setNavCategories(response.data);
    } catch (error) {
      console.error('Failed to fetch nav categories:', error);
    } finally {
      setLoadingCategories(false);
    }
  };

  // --- Trending rotation ---
  useEffect(() => {
    if (trendingData.length === 0 || isHovering) return;
    const interval = setInterval(() => {
      setTrendingIndex((prev) => (prev + 1) % trendingData.length);
      setAnimationKey(prev => prev + 1);
    }, 3000);
    return () => clearInterval(interval);
  }, [trendingData, isHovering]);

  const fetchTrendingNews = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/trending`, {
        withCredentials: true
      });
      const result = response.data;
      if (result.type === 'weather') {
        setDataType('weather');
        const weatherArray = Array.isArray(result.data) ? result.data : [result.data];
        setTrendingData(weatherArray);
      } else {
        setDataType('trending');
        setTrendingData(result.data || []);
      }
      setTrendingIndex(0);
    } catch (error) {
      console.error('Failed to fetch trending news:', error);
    } finally {
      setLoadingTrending(false);
    }
  };

  const nextTrending = () => {
    if (trendingData.length > 0) {
      setTrendingIndex((prev) => (prev + 1) % trendingData.length);
      setAnimationKey(prev => prev + 1);
    }
  };

  const prevTrending = () => {
    if (trendingData.length > 0) {
      setTrendingIndex((prev) => (prev - 1 + trendingData.length) % trendingData.length);
      setAnimationKey(prev => prev + 1);
    }
  };

  const renderCurrentContent = () => {
    if (loadingTrending) return "Loading...";
    if (trendingData.length === 0) return "Welcome to RootNetwork!";
    const item = trendingData[trendingIndex];
    if (dataType === 'weather') {
      return (
        <span>
          <span className="me-1">{item.icon || '🌡️'}</span>
          {item.city}: {item.temp}°C, {item.condition}
        </span>
      );
    } else {
      return item.headline;
    }
  };

  const getLabelText = () => {
    if (loadingTrending) return "Loading:";
    if (dataType === 'weather') return "Weather Update:";
    return "Trending Now:";
  };

  // --- Registration status ---
  useEffect(() => {
    checkRegistrationStatus();
  }, []);

  const checkRegistrationStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/check-registration-status`, {
        withCredentials: true
      });
      setRegistrationOpen(response.data.registration_open);
    } catch (error) {
      console.error('Failed to check registration status', error);
    }
  };

  // --- Profile image ---
  useEffect(() => {
    setImageError(false);
    if (adminData?.profile_image) {
      if (adminData.profile_image.startsWith('http')) {
        setProfileImageUrl(adminData.profile_image);
      } else if (adminData.profile_image && adminData.profile_image !== 'default-avatar.png') {
        setProfileImageUrl(`${API_URL}/static/${adminData.profile_image}`);
      } else {
        setProfileImageUrl(null);
      }
    } else {
      setProfileImageUrl(null);
    }
  }, [adminData]);

  const getUserInitial = () => {
    if (adminData?.full_name) return adminData.full_name.charAt(0).toUpperCase();
    if (adminData?.username) return adminData.username.charAt(0).toUpperCase();
    return 'U';
  };

  const handleImageError = () => {
    setImageError(true);
    setProfileImageUrl(null);
  };

  const isCategoryActive = (categorySlug) => {
    return location.pathname === `/category/${categorySlug}`;
  };

  return (
    <>
      {/* Topbar - exact same as your local version */}
      {showTopbar && (
        <div className="topbar bg-dark text-white py-2">
          <div className="container">
            <div className="d-flex align-items-center justify-content-between flex-wrap">
              <div className="d-flex align-items-center gap-2">
                <span className="text-uppercase text-danger me-2 fw-bold">
                  {getLabelText()}
                </span>
                {!loadingTrending && trendingData.length > 0 ? (
                  <div 
                    className="d-flex align-items-center gap-2"
                    onMouseEnter={() => setIsHovering(true)}
                    onMouseLeave={() => setIsHovering(false)}
                  >
                    <button onClick={prevTrending} className="btn btn-link text-white p-0 me-1" style={{ fontSize: '12px', textDecoration: 'none' }}>
                      <i className="fas fa-chevron-left"></i>
                    </button>
                    <span key={animationKey} className="trending-text" style={{ display: 'inline-block', animation: 'fadeInOut 0.5s ease', minWidth: '300px' }}>
                      {renderCurrentContent()}
                    </span>
                    <button onClick={nextTrending} className="btn btn-link text-white p-0 ms-1" style={{ fontSize: '12px', textDecoration: 'none' }}>
                      <i className="fas fa-chevron-right"></i>
                    </button>
                    {trendingData.length > 1 && (
                      <div className="d-flex gap-1 ms-2">
                        {trendingData.map((_, idx) => (
                          <button
                            key={idx}
                            onClick={() => { setTrendingIndex(idx); setAnimationKey(prev => prev + 1); }}
                            className={`rounded-circle p-0 border-0 ${idx === trendingIndex ? 'bg-danger' : 'bg-secondary'}`}
                            style={{ width: '6px', height: '6px', opacity: idx === trendingIndex ? 1 : 0.5 }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="trending-text text-muted">
                    {!loadingTrending && 'No updates at the moment'}
                  </span>
                )}
              </div>
              <div className="d-flex gap-3 mt-2 mt-sm-0">
                <span><i className="fas fa-map-marker-alt me-1"></i> Worldwide</span>
                <Link to="/about" className="text-white text-decoration-none">About</Link>
                <Link to="/contact" className="text-white text-decoration-none">Contact</Link>
                <div className="d-flex gap-2">
                  <a href="#" className="text-white"><i className="fab fa-facebook-f"></i></a>
                  <a href="#" className="text-white"><i className="fab fa-twitter"></i></a>
                  <a href="#" className="text-white"><i className="fab fa-youtube"></i></a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Navbar */}
      <nav className={`navbar navbar-expand-lg navbar-light bg-white main-navbar ${scrolled ? 'scrolled' : ''}`}>
        <div className="container">
          <a className="navbar-brand" href="#" onClick={(e) => { e.preventDefault(); navigate('/'); }} style={{ padding: '0' }}>
            <img src="/RootNetwork-logo.svg" alt="RootNetwork" style={{ height: '50px', width: 'auto', maxWidth: '200px' }} />
          </a>
          <button className="navbar-toggler" type="button" onClick={() => setIsOpen(!isOpen)}>
            <span className="navbar-toggler-icon"></span>
          </button>
          <div className={`collapse navbar-collapse ${isOpen ? 'show' : ''}`}>
            <ul className="navbar-nav ms-auto mb-2 mb-lg-0 align-items-center">
              <li className="nav-item">
                <a className={`nav-link ${location.pathname === '/' ? 'active fw-bold' : ''}`} href="#" onClick={(e) => { e.preventDefault(); navigate('/'); }}>
                  <i className="fas fa-home me-1"></i> Home
                </a>
              </li>
              {!loadingCategories && navCategories.map((category) => (
                <li className="nav-item" key={category.id}>
                  <a className={`nav-link ${isCategoryActive(category.slug) ? 'active fw-bold' : ''}`} href="#" onClick={(e) => { e.preventDefault(); navigate(`/category/${category.slug}`); }}>
                    {category.name}
                  </a>
                </li>
              ))}
              <li className="nav-item">
                <a className={`nav-link ${location.pathname === '/blog' ? 'active fw-bold' : ''}`} href="#" onClick={(e) => { e.preventDefault(); navigate('/blog'); }}>
                  Latest
                </a>
              </li>
              <li className="nav-item">
                <a className={`nav-link ${location.pathname === '/about' ? 'active fw-bold' : ''}`} href="#" onClick={(e) => { e.preventDefault(); navigate('/about'); }}>
                  About
                </a>
              </li>
              {isLoggedIn && (
                <li className="nav-item dropdown">
                  <a className="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                    <i className="fas fa-cog me-1"></i> Manage
                  </a>
                  <ul className="dropdown-menu">
                    <li><a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); navigate('/admin'); }}><i className="fas fa-tachometer-alt me-2"></i> Dashboard</a></li>
                    <li><a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); navigate('/admin/create'); }}><i className="fas fa-plus-circle me-2"></i> New Post</a></li>
                    <li><hr className="dropdown-divider" /></li>
                    <li><a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); navigate('/profile'); }}><i className="fas fa-user-circle me-2"></i> Profile</a></li>
                  </ul>
                </li>
              )}
              <li className="nav-item ms-lg-2 mt-2 mt-lg-0">
                {isLoggedIn ? (
                  <div className="d-flex align-items-center gap-2">
                    <div className="rounded-circle bg-primary d-flex align-items-center justify-content-center text-white" style={{ width: '36px', height: '36px', cursor: 'pointer', overflow: 'hidden', backgroundColor: (!profileImageUrl || imageError) ? '#667eea' : 'transparent' }} onClick={() => navigate('/profile')}>
                      {profileImageUrl && !imageError ? (
                        <img src={profileImageUrl} alt="Profile" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={handleImageError} />
                      ) : (
                        <span style={{ fontSize: '16px', fontWeight: 'bold' }}>{getUserInitial()}</span>
                      )}
                    </div>
                    <span className="badge bg-secondary px-3 py-2 rounded-pill">
                      <i className="fas fa-user-circle me-1"></i> {adminData?.username}
                    </span>
                    <button className="btn btn-outline-danger btn-sm rounded-pill px-3" onClick={handleLogout}>
                      <i className="fas fa-sign-out-alt me-1"></i> Logout
                    </button>
                  </div>
                ) : null}  {/* <-- NO login/register buttons */}
              </li>
            </ul>
          </div>
        </div>
      </nav>

      <style>{`
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateY(5px); }
          10% { opacity: 0; }
          20% { opacity: 1; transform: translateY(0); }
          80% { opacity: 1; }
          100% { opacity: 0; transform: translateY(-5px); }
        }
        .trending-text { display: inline-block; }
        .topbar button { background: transparent; border: none; color: white; cursor: pointer; transition: opacity 0.3s ease; }
        .topbar button:hover { opacity: 0.7; }
        .nav-link.active { color: #e74c3c !important; border-bottom: 2px solid #e74c3c; }
        .nav-link { transition: all 0.3s ease; }
        .nav-link:hover { color: #e74c3c !important; }
        .topbar { position: relative; z-index: 999; transition: transform 0.3s ease, opacity 0.3s ease; }
        .main-navbar { position: sticky; top: 0; z-index: 1000; background: white; transition: box-shadow 0.3s ease; }
        .main-navbar.scrolled { box-shadow: 0 4px 15px rgba(0,0,0,0.15); }
        .navbar-brand img { transition: transform 0.3s ease; }
        .navbar-brand img:hover { transform: scale(1.05); }
      `}</style>
    </>
  );
}

export default Navbar;
